# Diagram Guide

This folder stores editable reference diagrams for the project.

## Existing diagrams

- `pipeline-flow.drawio`: end-to-end execution flow
- `system-architecture.drawio`: module architecture and outputs

## Add a new reference diagram

1. Open [diagrams.net](https://app.diagrams.net/).
2. Open one of the existing `.drawio` files as a template.
3. Duplicate and rename it to `topic-name.drawio`.
4. Keep node names aligned with real code paths and CLI flags.
5. Save the new file under `docs/diagrams/`.
6. Add a link in `README.md` under `Reference Diagrams`.

## Optional: export preview image

If you want image previews instead of only source files:

1. In diagrams.net, click `File -> Export as -> SVG` (or PNG).
2. Save to `docs/diagrams/topic-name.svg`.
3. Embed in `README.md`:

```md
![topic-name](docs/diagrams/topic-name.svg)
```
