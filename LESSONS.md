# LESSONS: the evidence behind the playbook
Five finished competitions (3,500–6,425 teams each): four compared against top write-ups (1st place for BirdCLEF+ and ROGII, a third-party summary of the 1st place for RSNA, 12th place for BioHub), the LLM maths-reasoning one against forum posts.
Pattern: in four of five, the top team we compared against (line 2) owned a trained component of the winning type (or the winning labels); better final picks alone moved little.
Laws in `PLAYBOOK.md` cite these IDs. [n] = from another team's write-up or a summary of it (Sources, below).

## The five competitions
| comp | what the top team compared did | the winners' edge | lesson |
|---|---|---|---|
| LLM maths reasoning (~3,500 teams) | (forum) the same open model as everyone; time budget and answer selection on hard problems | porting the strongest public notebook alone was worth +3 problems; a 10-problem eval with 1 hard item could not rank changes | port the proven baseline day 0; eval shaped like the hard items (L34) |
| [BirdCLEF+](https://www.kaggle.com/competitions/birdclef-2026) (audio, ~4,100) | 5 s EfficientNetV2 distilled from Perch, 2 noisy-student rounds (+0.015 [1]), diverse ensemble | CV did not hold out the unseen site (OOF .087 above the board); winners trained pseudo-labels into the backbone, not the head | own model from day 1; hold out the decisive axis (L1, L4, L5) |
| [ROGII](https://www.kaggle.com/competitions/rogii-wellbore-geology-prediction) (well alignment, ~6,200) | distribution over depth: cost volume → 2-D U-Net, per-column CE, decode by expectation [2] | selectors + particle filter vs a learned distribution; an unpriced "no ML" constraint taken from a forum paraphrase | rate check weekly; price constraints (L11, L17, L19) |
| [BioHub](https://www.kaggle.com/competitions/biohub-cell-tracking-during-development) (cell tracking, ~4,000) | what a 12th-place team did [3]: learned stages per error cause inside an ILP, from the same public weights, one shipped every ~4 days | that team gained +0.025 private in four weeks (+0.049 over six) by shipping a measured stage every ~4 days [3] | ship one structural change a week (L3, L27) |
| [RSNA knee](https://www.kaggle.com/competitions/rsna-knee-abnormality-detection) (MRI, 6,425) | LLM agent reading report + images with zoom → labels (.936 vs .893 report-only; per a third-party summary, most of the gap was labels [4]); site term in training only [5] | label-bound from day 0 (58 of 4,407 exams labelled); round-1 labels (LLM report labels mixed 50/50 with model OOF) plus a denser input cache raised public by .017 like-for-like (5 folds, vs control e010; CV +.034, inflated by those labels); the winners added image reading with zoom | the strongest version, or the lane isn't closed (L1, L2, L12) |

## Lessons
| ID | lesson | evidence |
|---|---|---|
| L1 | A lane is dead only after its elite version ran. | RSNA: image reading closed on two cheap blind tests; the winners' elite version (LLM + report + zoom) was their biggest lever [4]. BirdCLEF: 5 head-only pseudo-label tries read "dead"; backbone noisy-student was the winner's #1 lever [1]. |
| L2 | Name the bottleneck day 0; compute follows it. | RSNA: label-bound from day 0 (58 of 4,407 exams labelled); round-1 labels + denser input: public +.017 vs control e010 (5 folds; label and input effects not separated). Later label rounds' CV gains are inflated by OOF-blended labels, so not comparable with model levers (≤ +.002); now a check in `kit/templates/train.py` (`LABELS_FROM_OOF`). |
| L3 | Weekly shipped structural stages beat knob-tuning (one team); diagnosis not built that week is worth little until built. | BioHub: from the same public weights, a team shipping a measured stage every ~4 days gained +0.025 private in four weeks (+0.049 over six) [3]. |
| L4 | Strongest simple recipe, trained by us, is the base; public base + knobs caps you. | RSNA: one-fold ConvNeXt-T matched a 3-stage chain. BirdCLEF: ~37 knob/post-proc transfers = 0. |
| L5 | Hold out the hardest hidden axis; group-honest CV still misleads if the decisive axis is not held out. | BirdCLEF: grouped OOF .087 above the board, unseen site not held out. ROGII: private = harder wells. |
| L6 | A ruler tracks board order before deciding, per change type; a small expert set is a weak ruler (RSNA: 58 exams, about ±.02 macro-AUC noise). | RSNA: a 58-exam expert set tracked public-board order at Spearman ρ = .07 over 13 subs (vs .884 for fold-0 CV); the ruler now uses the residual SD around a linear fit (law 4). |
| L7 | The tail carries the loss; report the tail score (`oof_hard`) every run. | ROGII: 10 % of wells = 56 % of squared error. |
| L8 | Public boards misvalue tail levers; classify broad vs tail first. | ROGII: −0.006 public lever = −0.622 private (8.488 → 7.866); the gate acted only on ~12 % of wells, the hard ones. |
| L9 | LLMs as data factories: tier readers (cheap first, strong on disputes). | RSNA: LLM reading of 4,349 reports gave the labels every model trained on; round-1 labels (those mixed 50/50 with model OOF) + a denser cache (72 slices per exam instead of 44; own records, not published): public +.017 vs control e010 (5 folds; CV +.034, inflated by those labels); later label rounds +.002 to +.006 CV each (CV; rounds that blend model OOF into the labels inflate it, as in e014) at ~0 GPU. The 1st place's LLM labels: .936 vs .893 report-only [4]. |
| L10 | Read top-10 hints literally; test the plain reading in 48 h. | RSNA: "don't rely on reports alone" meant "look at the images", the winners' lever [4]. |
| L11 | A converged ceiling belongs to a channel, not the problem. | ROGII: a ceiling confirmed many ways for one channel; per-column CE on the same information reached CV 5.09 alone, 4.63 in the 1st-place ensemble [2]. |
| L12 | Audit shortcuts on raw inputs; remove them in training, not at test. | RSNA: metadata AUC .65 hid a site shortcut; a training-only site term gave +.014 [5]; test-time corrections did not help. |
| L14 | Measure in the deployed form. | ROGII: −0.25 ranker gain was a leak through the candidate set (honest −0.05). RSNA: +.0023 → +.0014 in the blend. |
| L15 | Day 0: what were provided weights trained on? | BioHub: public detectors had seen the train movies → in-sample bench, ~0.03 over-read [3]. |
| L16 | Proxies may not even rank; the first real signal is end to end. | RSNA: ~30 frozen-feature proxies did not predict full training; a head-only lab ranked label sets opposite to it. |
| L17 | The weekly rate check fires when a route stalls; read the rate on CV, not public. | ROGII (error, lower is better): in the 11 days after v27 (07-24), other changes cut private error by 0.189 while the best public score moved 0.003; the rate check now reads CV (`plateau`). |
| L18 | Estimate, don't select; weak signals as soft gated inputs. | ROGII: the 1st place decoded by expectation [2]. |
| L19 | Price every constraint before adopting it; a competitor's forum paraphrase is not a rule. | ROGII: a "no ML" claim came from a team running a ~1B-param CNN ensemble. |
| L21 | Idle compute is the cheapest loss; a standing budget beats per-run owner approval. | RSNA: per-run owner approval left 26 of 30 weekly GPU-h idle. BioHub: analysis kernels took 62 % of quota → ≤ 20 % cap. |
| L22 | Price the winning type's training cost on day 0. | ROGII: 1st place's weakest model (~8 GPU-h) alone beat the gold cut [2]. |
| L24 | In RSNA, ROGII and BirdCLEF the winning recipe was in our intel before halfway (seen in hindsight). | RSNA week-0 intel; ROGII per-column CE in a mid-campaign plan; BirdCLEF distillation noted early. |
| L27 | Knobs tuned on a small public board don't transfer; stages do. | BioHub: last week +0.008 public / +0.001 private; the unified ILP linker (a stage, not a knob) was the only late change that gained private, +.003–.004 (own records, not published). |
| L32 | Pseudo-labels paid when they trained the backbone, with the pseudo-label sum capped below the focal-label sum; head-only did not (BirdCLEF). | BirdCLEF 1st: two noisy-student rounds .935 → .950 [1]. |
| L34 | Runtime-bound comps are won by speed per item. | LLM maths: top teams ran the same open model (forum); the gap was time spent on hard problems. |
| L35 | My agent team cost more than it shipped; measure coordination share before adding agents. | RSNA: a manager + 4 workers cost 78 weighted M tokens a day, 1,840 messages, 38 pushes and 0 submissions in 2.9 days (44 % of spend was coordination; a TPU queue also blocked). One lead + one-shot helpers cost 36 a day and resumed submissions. Before the team, the solo lead ran 10 days at a median 324k context, cache reads 63 % of cost. Not a controlled comparison; the cheapest week (16 a day, solo) gave the largest gain. |

Checklist (standard practice): **L13** a feature imputed from neighbouring groups leaks under random folds; check it on group-disjoint folds (ROGII: KNN feature LB 1.04 worse than CV) · **L20** pick finals by CV plus one decorrelated hedge, never two public-best of one family (BirdCLEF: the unpicked decorrelated fork scored private .94216, at the bronze cut) · **L23** verify every rule at the source (BirdCLEF: "external banned" and "no unlabelled soundscapes" both false) · **L25** big levers first, tweaks while they train; commit day = queue + one retry (RSNA: a late big lever queued 16.6 h left no retry slot) · **L26** measure rank correlation before adding a blend member (RSNA: variants at .96–.98 added nothing on the board) · **L28** a late entry leaves no retry slot for a big lever (RSNA: 3 weeks left) · **L29** levers for weak bases vanish on strong ones (see L4) · **L30** look at individual errors before inventing arms (RSNA: rendering errors as the model sees them found the mechanism in hours) · **L31** cuts move; tie-blocks are forked notebooks (BioHub: 305 teams at one score; bronze cut +0.009 in 5 days) · **L33** read the host's own pages before treating a question as open (ROGII: breakthrough signal in a host slide; BioHub: split stated on the data page).

## Priors by problem type (day-0 guesses from one competition each; the competition's own evidence overrides them) (no tabular competition yet)
| problem | what wins | trap | evidence |
|---|---|---|---|
| image, label-bound | ConvNeXt-class + LLM label machine (text + images with zoom) + 1–2 self-distill rounds; site term in training only | blends of near-copies; test-time site fixes | L2, L9, L12, L26 [4][5] |
| detection / tracking | learned stages per error cause, learned costs inside the ILP, a detector trained by us (public ones may have seen the train set) | knobs on a one-group public board | L3, L15, L27 [3] |
| signal alignment | cost volume → 2-D U-Net → per-column CE, decode by expectation | regressing the path, selectors | L11, L18 [2] |
| audio | own distilled 5 s SED + 2 noisy-student rounds into the backbone | head-only pseudo-labels, unseen site not in CV | L1, L5, L32 [1] |
| LLM reasoning | port the best public notebook day 0; time budget per hard item, early stop, tools | prompt tweaks on an easy eval | L34 (forum) |

## Sources
[1] BirdCLEF+ 1st place, "Noisy Student Meets Distillation": https://www.kaggle.com/competitions/birdclef-2026/discussion/704752
[2] ROGII 1st place: https://www.kaggle.com/competitions/rogii-wellbore-geology-prediction/discussion/733220
[3] BioHub 12th place (Table 1, stage-by-stage private scores): https://www.kaggle.com/competitions/biohub-cell-tracking-during-development/discussion/744501
[4] RSNA knee 1st place, as summarised by a third party: https://github.com/Catejsj/rsna-knee-2026/blob/main/WRITEUP.md
[5] RSNA knee write-up digest (33rd place: training-only site term +.014): https://github.com/TaeyanG4/rsna-knee-abnormality-detection
