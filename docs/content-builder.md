# Content Builder

ArcHub Content Builder stores structured blocks as JSON in content payloads and
renders them into safe public HTML.

## Built-in block groups

- hero;
- rich text;
- call to action;
- feature grid;
- FAQ;
- quote;
- media;
- API action;
- RAG reference;
- expert list;
- token plans;
- workflow steps;
- download;
- embed;
- metrics.

## Validation

Each block type has declared fields, defaults, editor hints and required flags.
Draft save and publish normalize blocks through the same registry, so invalid
blocks fail before they reach published delivery.
