"""The repo checks itself: every ID cited exists, README counts match, documented alerts are emitted.
Offline: python3 -m unittest discover -s tests (the whole suite, about 30 s)"""
import re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".md", ".py", ".sh", ".json", ".yml")
        and ".git" not in p.parts and "competitions" not in p.parts]
TEXT = {p: p.read_text(errors="replace") for p in DOCS}
ALL = "\n".join(TEXT.values())
LESSON_ID = r"(?:^\| |\*\*)(L\d+)(?: \||\*\*)"     # table rows, and the bold IDs on the "Checklist" line


def defined(path, pat):
    return set(re.findall(pat, (ROOT / path).read_text(), re.M))


class Consistency(unittest.TestCase):
    def test_cited_ids_exist(self):
        have = {"R": defined("RULES.md", r"^- \*\*(R\d+)\*\*"), "L": defined("LESSONS.md", LESSON_ID),
                "T": defined("TOOLING.md", r"^- \*\*(T\d+)\b")}
        for kind, ids in have.items():
            cited = set(re.findall(rf"\b({kind}\d+)\b", ALL))
            self.assertFalse(cited - ids, f"{kind} IDs cited but not defined: {sorted(cited - ids)}")
        laws = {int(n) for n in defined("PLAYBOOK.md", r"^(\d+)\. \*\*")}
        cited = {int(n) for n in re.findall(r"\blaws? (\d+)\b", ALL)} | \
                {int(n) for a, b in re.findall(r"\blaws (\d+)[–-](\d+)", ALL) for n in (a, b)}
        self.assertFalse(cited - laws, f"laws cited but not defined: {sorted(cited - laws)}")
        secs = set(re.findall(r"^## (\d+)\.", (ROOT / "PLAYBOOK.md").read_text(), re.M))
        self.assertFalse(set(re.findall(r"§(\d+)", ALL)) - secs, "PLAYBOOK § cited but missing")

    def test_readme_counts(self):
        r = (ROOT / "README.md").read_text()
        n = {"lessons": len(defined("LESSONS.md", LESSON_ID)), "traps": len(defined("TOOLING.md", r"^- \*\*(T\d+)\b")),
             "laws": len(defined("PLAYBOOK.md", r"^(\d+)\. \*\*"))}
        pats = {"lessons": r"(\d+) lessons\b", "traps": r"(\d+) (?:Kaggle and compute )?traps\b", "laws": r"(\d+) rules of thumb\b"}
        for word, count in n.items():
            claims = re.findall(pats[word], r)
            self.assertTrue(claims, f"README states no count of {word}")
            for claimed in claims:
                self.assertEqual(int(claimed), count, f"README says {claimed} {word}, files have {count}")
        def ids(suite):
            for t in suite:
                yield from ids(t) if isinstance(t, unittest.TestSuite) else [t]
        found = ids(unittest.TestLoader().discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests")))
        tests = sum(1 for t in found if "extras" not in Path(sys.modules[type(t).__module__].__file__).parts)   # what the public repo's runner prints
        for claimed in re.findall(r"(\d+) offline tests", r):
            self.assertEqual(int(claimed), tests, f"README says {claimed} tests, there are {tests}")
        skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertGreaterEqual(len(skills), 10, "skills/ is missing skills")
        listed = set(re.findall(r"`([a-z-]+)`", (ROOT / "CLAUDE.md").read_text())) & (skills | {"x"})
        self.assertEqual(listed, skills, "CLAUDE.md skill list != skills/")

    def test_skill_frontmatter(self):
        for p in (ROOT / "skills").glob("*/SKILL.md"):
            head = p.read_text().split("---")[1]
            self.assertIn(f"name: {p.parent.name}\n", head, p)
            self.assertRegex(head, r"\ndescription: .{40,}", p)

    def test_documented_alerts_are_emitted(self):
        w = (ROOT / "kit" / "watcher.sh").read_text()
        emitted = set(re.findall(r"\b(?:alert|once) \"?([a-z0-9][a-z0-9-]*[a-z0-9])", w)) | set(re.findall(r"once \"([a-z]+)-", w))
        for p, t in TEXT.items():
            if p.name == "watcher.sh":
                continue
            for key in re.findall(r"(?:alert|alerts?) `([a-z0-9-]+)`|`([a-z0-9-]+)` alerts?\b", t):
                k = key[0] or key[1]
                self.assertIn(k, emitted, f"{p.relative_to(ROOT)} names alert '{k}' that watcher.sh never emits")

    def test_gitignore_keeps_records_and_drops_data(self):
        import shutil, subprocess, tempfile
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(ROOT / ".gitignore", d)
            subprocess.run(["git", "init", "-q", d], check=True)
            ign = lambda p: subprocess.run(["git", "-C", d, "check-ignore", "-q", p]).returncode == 0
            for p in ("competitions/x/data/folds.npy", "competitions/x/data/hard_ids.npy", "competitions/x/experiments.csv",
                      "competitions/x/code/k1/k1.py", "competitions/x/runs/k1/v1/train.log"):
                self.assertFalse(ign(p), f"{p} must be committed")
            for p in ("competitions/x/data/train.csv", "competitions/x/oof/e1.npy", "competitions/x/runs/k1/v1/model.pt"):
                self.assertTrue(ign(p), f"{p} must stay out of git")

    def test_experiments_header_is_one(self):
        heads = set(re.findall(r"id,date,change,kind[a-z_,]+note", ALL))
        self.assertEqual(len(heads), 1, f"experiments.csv header differs between files: {heads}")


if __name__ == "__main__":
    unittest.main()
