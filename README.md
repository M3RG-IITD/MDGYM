# MDGYM: Benchmarking AI Agents on Molecular Simulations

<div align="center">

<img src="assets/MDGYM_logo.svg" alt="MDGYM Logo" width="400"/>

📄 [Paper](https://arxiv.org/pdf/2605.08941)

</div>

MDGYM is a benchmark for evaluating AI agents on molecular dynamics (MD) simulation
tasks. Each task gives an agent a natural-language problem description — a system to
build, a set of simulation parameters, and a physical property to compute — and asks
it to produce a numeric result that is checked against a held-out ground truth.

## Dataset 

Tasks are organized by simulation engine:

| Engine  | Tasks |
|---------|-------|
| GROMACS | 75   |
| LAMMPS  | 94    | 
| **Total** | **169** |

## Leaderboard 🏆

| Rank | Model | Harness | Easy | Medium | Hard | Overall |
|------|-------|---------|------|--------|------|---------|
|1	| Claude Opus 4.8	| OpenHands	| 68.4%	| 34.5%	| 24.6% | 52.3% |
|2	| DeepSeek-V4 Pro	| OpenHands	| 43.9%	| 20.0%	| 8.8% | 24.2% |
|3	| GPT-OSS 20B	| OpenHands	| 0%	| 0%	| 0% | 0% |
|4	| Qwen3-Coder	| OpenHands	| 2%	| 0%	| 0% | 0% |


### Submitting to the leaderboard

Run your model/harness on the dataset and write us at vinay.kumar@scai.iitd.ac.in, krishan@iitd.ac.in and mausam@iitd.ac.in. We will evaluate your submission against the held-out ground truth values.

## Citation

If you use MDGYM in your work, please cite:

```
Kumar, Vinay, Satyendra Rajput, and N. M. Krishnan. "MDGYM: Benchmarking AI Agents on
Molecular Simulations." ArXiv, (2026). Accessed September 10, 2026.
https://arxiv.org/abs/2605.08941.
```
