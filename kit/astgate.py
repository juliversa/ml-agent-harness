#!/usr/bin/env python3
"""Pre-push code gate. Three checks, in the order they have actually bitten:
  1 compile()  -- catches a displaced `from __future__` that ast.parse() accepts
  2 module-level DEFINITION-BEFORE-USE -- catches a forward reference that BOTH accept
  3 function-body free names must resolve somewhere in the module
"""
import ast, builtins, sys

COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)   # own scope: their loop variables do not leak

def gate(path):
    src = open(path).read()
    compile(src, path, "exec")                     # check 1
    tree = ast.parse(src)
    if any(a.name == "*" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names):
        return print(f"GATE PASS {path}: compile OK; name checks SKIPPED (star import)")
    defined = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__class__", "__builtins__"}

    def binds(node):
        out = set()
        for n in ast.walk(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): out.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names: out.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store): out.add(n.id)
            elif isinstance(n, ast.arg): out.add(n.arg)
            elif isinstance(n, ast.ExceptHandler) and n.name: out.add(n.name)
            elif isinstance(n, ast.Global): out.update(n.names)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name: out.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest: out.add(n.rest)
        return out

    def module_binds(stmt):
        """Names a module-level statement binds: descend into if/for/with/try, never into def/class/lambda bodies."""
        out, todo = set(), [stmt]
        while todo:
            n = todo.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name); continue
            if isinstance(n, ast.Lambda): continue
            if isinstance(n, COMPS):                 # only a walrus inside binds in the enclosing scope
                out |= {x.target.id for x in ast.walk(n) if isinstance(x, ast.NamedExpr)}; continue
            out |= binds(n) if isinstance(n, (ast.Import, ast.ImportFrom)) else set()
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store): out.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name: out.add(n.name)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name: out.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest: out.add(n.rest)
            todo.extend(ast.iter_child_nodes(n))
        return out

    def import_time_loads(node):
        res = []
        def walk(n, cls=frozenset()):              # cls: names visible here that the module does not bind (class body, comprehension)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                for d in getattr(n, "decorator_list", []): walk(d, cls)
                a = n.args
                for d in a.defaults + [x for x in a.kw_defaults if x]: walk(d, cls)
                return
            if isinstance(n, ast.ClassDef):          # a class body runs top to bottom at import, in its own scope
                for d in n.decorator_list + n.bases + [k.value for k in n.keywords]: walk(d, cls)
                own = set(cls)
                for s in n.body: walk(s, frozenset(own)); own |= module_binds(s)
                return
            if isinstance(n, COMPS):                 # its own scope: sees its `for` targets, not class-body names,
                walk(n.generators[0].iter, cls)      # except in the first iterable, evaluated outside
                inner = frozenset(getattr(n, "_comp", frozenset())) | {x.id for g in n.generators for x in ast.walk(g.target) if isinstance(x, ast.Name)}
                for c in ast.walk(n):
                    if isinstance(c, COMPS) and c is not n: c._comp = inner   # a nested comprehension sees these
                for i, g in enumerate(n.generators):
                    if i: walk(g.iter, inner)
                    for c in g.ifs: walk(c, inner)
                for part in ("elt", "key", "value"):
                    if getattr(n, part, None) is not None: walk(getattr(n, part), inner)
                return
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in cls: res.append(n)
            for c in ast.iter_child_nodes(n): walk(c, cls)
        walk(node); return res

    fwd = []
    for stmt in tree.body:                          # check 2
        own = module_binds(stmt)
        for nm in import_time_loads(stmt):
            if nm.id not in defined and nm.id not in own: fwd.append((nm.lineno, nm.id))
        defined |= own
    if fwd:
        raise SystemExit(f"FORWARD REFERENCE at module level in {path}: "
                         + ", ".join(f"line {l}: {n}" for l, n in fwd[:20]))

    defined |= {g for n in ast.walk(tree) if isinstance(n, ast.Global) for g in n.names}   # `global x` in a function
    missing = set()                                 # check 3 (outermost functions; their walk covers nested ones,
    fns = (ast.FunctionDef, ast.AsyncFunctionDef)   # whose names may come from the enclosing scope)
    inner = {id(c) for n in ast.walk(tree) if isinstance(n, fns) for c in ast.walk(n) if c is not n and isinstance(c, fns)}
    for n in ast.walk(tree):
        if isinstance(n, fns) and id(n) not in inner:
            local = binds(n)
            for x in ast.walk(n):
                if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) \
                   and x.id not in local and x.id not in defined:
                    missing.add((x.lineno, x.id))
    if missing:
        raise SystemExit(f"UNRESOLVED function-body names in {path}: {sorted(missing)[:20]}")
    print(f"GATE PASS {path}: compile OK, no module-level forward refs, no unresolved globals")

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit("usage: astgate.py <file.py> [...]")
    for p in sys.argv[1:]: gate(p)
