# Chimeraforge Publish-Ready Reports

This directory is the canonical home for publication-ready technical reports,
conclusive synthesis volumes, and executive whitepapers.

## Scope

The current corpus spans:

- Phase 1: Foundation (`TR108-TR122`)
- Phase 2: Deployment Framework (`TR123-TR133`)
- Phase 3: Automation and Evaluation (`TR134-TR137`)

## Numbered Technical Reports

### Phase 1: Foundation

| Report | File |
|--------|------|
| TR108 | `Technical_Report_108.md` |
| TR109 | `Technical_Report_109.md` |
| TR110 | `Technical_Report_110.md` |
| TR111_v2 | `Technical_Report_111_v2.md` |
| TR112_v2 | `Technical_Report_112_v2.md` |
| TR113 | `Technical_Report_113.md` |
| TR114_v2 | `Technical_Report_114_v2.md` |
| TR115_v2 | `Technical_Report_115_v2.md` |
| TR116 | `Technical_Report_116.md` |
| TR117 | `Technical_Report_117.md` |
| TR117_multi_agent | `Technical_Report_117_multi_agent.md` |
| TR118_v2.2 | `Technical_Report_118_v2.2.md` |
| TR119 | `Technical_Report_119.md` |
| TR120 | `Technical_Report_120.md` |
| TR121v1 | `Technical_Report_121v1.md` |
| TR122 | `Technical_Report_122.md` |

### Phase 2: Deployment Framework

| Report | File |
|--------|------|
| TR123 | `Technical_Report_123.md` |
| TR124 | `Technical_Report_124.md` |
| TR125 | `Technical_Report_125.md` |
| TR126 | `Technical_Report_126.md` |
| TR127 | `Technical_Report_127.md` |
| TR128 | `Technical_Report_128.md` |
| TR129 | `Technical_Report_129.md` |
| TR130 | `Technical_Report_130.md` |
| TR131 | `Technical_Report_131.md` |
| TR132 | `Technical_Report_132.md` |
| TR133 | `Technical_Report_133.md` |

### Phase 3: Automation and Evaluation

| Report | File |
|--------|------|
| TR134 | `Technical_Report_134.md` |
| TR135 | `Technical_Report_135.md` |
| TR136 | `Technical_Report_136.md` |
| TR137 | `Technical_Report_137.md` |

## Conclusive Synthesis Sets

| Scope | Main | Appendices | Whitepaper |
|-------|------|------------|------------|
| 108-116 | `Technical_Report_Conclusive_108-116.md` | `Technical_Report_Conclusive_108-116_Extended_Appendices.md` | `Technical_Report_Conclusive_108-116_Whitepaper.md` |
| 117-122 | `Technical_Report_Conclusive_117-122.md` | `Technical_Report_Conclusive_117-122_Extended_Appendices.md` | `Technical_Report_Conclusive_117-122_Whitepaper.md` |
| 123-133 | `Technical_Report_Conclusive_123-133.md` | `Technical_Report_Conclusive_123-133_Extended_Appendices.md` | `Technical_Report_Conclusive_123-133_Whitepaper.md` |
| 134-137 | `Technical_Report_Conclusive_134-137.md` | `Technical_Report_Conclusive_134-137_Extended_Appendices.md` | `Technical_Report_Conclusive_134-137_Whitepaper.md` |

## Historical Drafts

Superseded drafts are retained under `historical/`:

- `historical/Technical_Report_111.md` -> `Technical_Report_111_v2.md`
- `historical/Technical_Report_112.md` -> `Technical_Report_112_v2.md`
- `historical/Technical_Report_114.md` -> `Technical_Report_114_v2.md`
- `historical/Technical_Report_115.md` -> `Technical_Report_115_v2.md`
- `historical/Technical_Report_118.md`, `historical/Technical_Report_118_v2.md`, and `historical/Technical_Report_118_v2.1.md` -> `Technical_Report_118_v2.2.md`
- `historical/Technical_Report_119v1.md` -> `Technical_Report_119.md`
- `historical/Technical_Report_121.md` -> `Technical_Report_121v1.md`

## Supporting Files

- `supporting/TR116_data.md`

## Related Paths

- `../../README.md`
  Overview of the whole outputs tree.
- `../../reports/README.md`
  Exploratory and legacy report outputs.
- `../docs/README.md`
  Publish-ready benchmark writeups and supporting notes.
- `../../../docs/technical_reports.md`
  Cross-linked index used by the docs site.

## Guidance

- Link this directory from documentation, PRs, and issues when citing TR-series work.
- Do not use `outputs/reports/` as the source of truth for the numbered report set.
- Keep experimental code and result artifacts in `experiments/`; keep stakeholder-facing
  report documents here.
