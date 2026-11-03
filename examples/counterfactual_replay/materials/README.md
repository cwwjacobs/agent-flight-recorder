# Delta materials

Files in this directory are the declared per-arm materials for the
counterfactual replay harness. A replay ticket's delta `ref` names one
file here; the arm handler (`../arm_handler.py`) loads it and puts it
in the arm's continuation prompt. Every arm's material is declared on
its ticket and in its trace, and (Step 4) in the receipt bundle — that
declaration is what keeps the arms honest.

Set `AFR_ARM_MATERIALS_DIR` to point the handler at another directory.

## Formats

- **generic context** (`generic_context`): a plain-text file, added
  verbatim. It must be generic domain context, NOT distilled from the
  recorded run — otherwise it collapses into the selected arm and the
  comparison lies.
- **selected cards** (`selected_cards`): a JSON file holding a list of
  cards, each `{"title": "...", "body": "..."}`. The handler renders
  each card as its title followed by its body.
- **oracle context** (`oracle_context`): a plain-text file with the
  known-correct resolution for the scenario. This is the upper-bound
  reference arm, labeled as such wherever results are shown — never a
  fair arm.
- **bare** (`none`): no file; nothing is added.

## What is NOT here

The demo scenario's actual material files (the generic checkout text,
the demo card set, the oracle text) are demo content, authored with
the demo — they are not part of the Step 2 mechanism build, so they
are deliberately absent. The driver's default refs name the expected
files (`generic-checkout-context.txt`, `demo-cards.json`,
`oracle-checkout.txt`); an arm whose material is missing fails loudly
instead of silently running bare.
