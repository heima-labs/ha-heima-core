# Heima v2 — Emotion-Oriented IEQ Research Note

**Status:** RFC / research reference  
**Scope:** external research analysis for possible future v2+ directions  
**Primary paper:** *Emotion-oriented recommender system for personalized control of indoor environmental quality*  
**DOI:** `10.1016/j.buildenv.2024.111396`

## 1. Purpose

This document captures the structured analysis of the paper:

- *Emotion-oriented recommender system for personalized control of indoor environmental quality*

The goal is not to treat the paper as an adopted architecture, but to preserve its ideas,
claims, and constraints as a future development reference for Heima v2 and later.

This note intentionally keeps information even when its applicability to Heima is uncertain.

## 2. Source Basis

The analysis below is based on:

- ScienceDirect preview / abstract page for the paper
- Yonsei / Elsevier Pure institutional publication record
- text visible from a Scribd mirror of the paper
- adjacent papers by the same research group for contextual corroboration

## 3. Reliability Legend

- `Confirmed`
  - consistent across multiple sources or clearly present in primary metadata/preview
- `Plausible but to verify`
  - coherent with visible text and surrounding papers, but not fully verified from primary full text
- `Not yet verifiable`
  - likely relevant, but not reliably confirmed from accessible sources

## 4. Analytical Table

| Theme | Information | Reliability | Technology Dependencies | Implications for Heima |
|---|---|---|---|---|
| Problem | Traditional IEQ systems rely mainly on explicit feedback and historical preferences, underusing emotional state | Confirmed | None specific | Suggests a layer above simple rules and preference memory |
| Problem | IEQ affects health, cognition, and mood | Confirmed | None specific | Supports broader comfort reasoning, not just static control |
| Problem | IEQ preferences are subjective and dynamic | Confirmed | None specific | Reinforces strong personalization requirements |
| Architecture | Proposed system name: `ERS-IEQ` | Confirmed | None specific | Useful as external conceptual reference |
| Architecture | System is organized via the `R-E-C-S` ontology | Confirmed | Ontology / conceptual framework | Could inspire future internal taxonomy |
| Architecture | The four blocks are recognizing emotions, estimating emotional similarity, collecting feedback, and systemizing the recommender | Confirmed | Multi-stage pipeline | Relevant as future decomposition pattern |
| Architecture | The exact formal definition of the ontology is fully known | Plausible but to verify | Ontological formalism | Requires fuller source access before reuse |
| Data | Dataset is private and built from experiments with human participants | Confirmed | Experimental protocol | Limits reproducibility, but confirms concrete data collection |
| Data | Data collection occurred in a climate/environmental chamber | Confirmed | Controlled chamber setup | Laboratory setting differs from real homes |
| Data | Number of users: `49` | Confirmed | Participant recruitment | Small by modern ML standards |
| Data | Number of IEQ conditions: `7` | Confirmed | IEQ test setup | Suggests limited experimental state space |
| Data | Sample size: `686` (`49 × 7 × 2`) | Confirmed | Dataset assembly | Useful, but not large |
| Data | Explicit labels include thermal preference and visual preference | Confirmed | Survey / labeling | Immediately relevant to heating and lighting domains |
| Data | Feedback uses a 7-point Likert scale | Confirmed | Questionnaire design | Could inspire explicit user feedback collection |
| Data | Dataset includes IEQ conditions, explicit feedback, and emotional states | Confirmed | Multimodal data collection | Richer than current Heima household data |
| Data | Full feature set and temporal granularity are fully known | Not yet verifiable | Full dataset and methods | Need complete source access before serious replication |
| Emotional modeling | Emotional state is modeled continuously | Confirmed | Emotion inference pipeline | More expressive than discrete mood flags |
| Emotional modeling | Multimodal sources include lifelogs, facial expressions, physiological signals, and voice | Confirmed | Sensors / multimodal fusion | Major jump in sensing complexity for Heima |
| Emotional modeling | Emotional similarity between users is modeled via Fuzzy Logic | Confirmed | Fuzzy inference system | Distinctive ingredient of the paper |
| Emotional modeling | The number of linguistic terms for emotional similarity matters strongly | Confirmed | Fuzzy linguistic variable design | Concrete design variable if ever replicated |
| Emotional modeling | Four linguistic terms performed best | Confirmed | Fuzzy design choice | Potential future heuristic reference |
| Emotional modeling | The exact fuzzy formulation and membership functions are fully known | Plausible but to verify | Fuzzy formalism | Requires full methodological detail |
| Emotional modeling | The paper discusses feature-level, decision-level, and model-level fusion | Plausible but strongly coherent | Multimodal fusion strategies | Helpful for classifying future Heima sensing pipelines |
| Recommender | The recommender is emotion-oriented, not just preference-oriented | Confirmed | Recommender pipeline | Important conceptual distinction |
| Recommender | The system uses graph neural network / graph attention network ideas | Confirmed | GNN / GAT | Substantially beyond Heima’s current runtime complexity |
| Recommender | Emotional similarity between users contributes to recommendation quality | Confirmed | User-user similarity + graph model | Relevant for multi-user homes |
| Recommender | The system aims to mitigate cold start and rating sparsity | Confirmed as a claim | Recommender design | Strong claim, needs careful quantitative reading |
| Recommender | Full graph structure, feature encoding, and baselines are fully known | Not yet verifiable | Full methods section | Must be verified before any replication effort |
| Results | `ERS-IEQ` significantly improves predictive performance | Confirmed | Evaluation pipeline | Central paper claim |
| Results | Improvement is particularly strong on thermal preference prediction | Confirmed | Thermal preference modeling | Highly relevant to heating |
| Results | Full numerical results for visual preference are available and verified | Not yet verifiable | Tables / metrics | Need full paper access |
| Results | Complete metrics and deltas vs baselines are known | Not yet verifiable | Evaluation tables | Required for serious benchmarking |
| Practical implications | Application to smart homes is explicitly claimed | Confirmed | Smart home stack | Direct thematic overlap with Heima |
| Practical implications | Potential use as a personal assistant for smart home automation | Confirmed | Assistive automation layer | Very close to Heima’s product direction |
| Practical implications | Possible use for elderly people or people with disabilities | Confirmed | Assistive technology context | Broadens accessibility framing |
| Practical implications | Light and temperature can be personalized using emotional context | Confirmed | IEQ control + emotion layer | Suggests future expansion of comfort intelligence |
| Observable limitations | Dataset is private | Confirmed | None | Weakens external reproducibility |
| Observable limitations | User count is only `49` | Confirmed | None | Generalization remains uncertain |
| Observable limitations | Validation is chamber-based, not long-running in real homes | Confirmed | Experimental setting | Real-world transfer risk |
| Observable limitations | Emotion sensing depends on potentially invasive or costly multimodal sensing | Observable from setup | CV, physiological sensing, voice, lifelogging | High barrier for domestic adoption |
| Observable limitations | Architecture is complex: ontology + emotion inference + fuzzy similarity + graph recommender | Observable | Advanced ML + structured modeling | Considerably more complex than current Heima |
| Observable limitations | Author-stated limitations from the full paper are completely known | Not yet verifiable | Full text | Needs full primary access |

## 5. Contextual Research Cluster

The paper appears to sit inside a broader Yonsei research line spanning:

- human-building interaction for indoor environmental control
- multimodal emotion recognition
- psychophysiological response to indoor environmental conditions
- preference modeling for thermal and visual comfort

This makes the paper look like a convergence point rather than an isolated experiment.

## 6. Use in Heima v2

This note does **not** imply adoption of:

- fuzzy emotional similarity
- graph neural recommenders
- multimodal emotion inference

It should instead be treated as:

- a future research reference
- a source of architectural vocabulary
- a catalog of ideas that may later be translated into simpler Heima-native forms

## 7. External References

- ScienceDirect preview: `https://www.sciencedirect.com/science/article/abs/pii/S0360132324002385`
- DOI: `https://doi.org/10.1016/j.buildenv.2024.111396`
- Yonsei / Elsevier Pure publication record:
  `https://yonsei.elsevierpure.com/en/publications/emotion-oriented-recommender-system-for-personalized-control-of-i/`
- Related Yonsei paper on multimodal emotion recognition:
  `https://yonsei.elsevierpure.com/en/publications/enhancing-emotion-recognition-using-multimodal-fusion-of-physiolo/`

