# Primary Sources Used by the Prototype

This file separates **current qualification facts**, **historical/legacy lab guidance**, and **simulated demo configuration**.

## Current Construction Electrician qualification

The current sector-skill-council source is CSDCI:

- Job role: **Construction Electrician-LV**
- QP code: **CON/Q0603**
- Level: **4**
- Current CSDCI Qualification Packs & Model Curriculums page marks the role **Active**:
  - https://www.csdcindia.org/qualification-packs-model-curriculums/
- CSDCI 2026 trainer/assessor results repeatedly reference **Construction Electrician LV V5 L4**:
  - https://www.csdcindia.org/tot-result-2026/
- Current V5 curriculum:
  - https://www.csdcindia.org/wp-content/uploads/2025/09/CON-Q0603.pdf

The NSDC occupational-standard export can surface older/retired records for the same code. For current-role status, this repository therefore uses the sector skill council's current qualification page rather than interpreting the older NSDC export entry as the current qualification state.

## Current V5 equipment-type evidence

The CSDCI V5 curriculum's module equipment lists explicitly include, among many other items:

- Digital Multimeter
- Drilling machine
- Cutting machine
- Chasing machine
- electrical sockets
- simple switchboard
- mains breaker
- ELCB / MCB
- water pumps
- bar cutting / bending machines
- PPE and safety equipment

The curriculum confirms these **types** are relevant to training. The module text does **not** provide sanctioned quantities for each item. KaushalWatch therefore does not infer quantities from this source.

## NSDC PMKK lab infrastructure guidance

NSDC's PMKK page lists a dedicated **Lab Specifications Electrician Construction** resource among the historical lab infrastructure guidelines:

- https://nsdcindia.org/pmkk

That guideline is useful design context for the idea of a standardized lab, but this repository does not silently treat legacy quantities as current PMKVY 4.0 sanctioned counts.

## Manifest provenance rules

In `configs/job_roles/construction_electrician.demo.json`:

- item **types** may cite the current CSDCI curriculum, the SIH problem-statement example, or legacy PMKK design context;
- every numeric `required` count is still explicitly **simulated** unless a current applicable quantity source is attached;
- a camera-verifiable class may intentionally group visually similar sanctioned items (for example switchboard/training-panel infrastructure), but the grouping must be disclosed;
- small/occluded tools such as a multimeter remain officer-verification candidates even when they are part of the curriculum.

A sourced job-role name or equipment type does not make a demo quantity official.
