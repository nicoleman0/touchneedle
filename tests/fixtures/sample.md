# A sample document

This fixture exercises the parser end to end. It deliberately contains an
earlier heading whose name collides with the real reference list, so that
`split_document` is forced to prefer the later one.

## References management

Reference lists in this project are maintained by hand. Nothing in this
section is a bibliography entry, so the splitter must not stop here.

## Findings

Prompt injection was first characterised at scale by Greshake et al. (2023),
and later formalised as an agent-level threat (Debenedetti et al., 2024).
The requirement-level vocabulary (Bradner, 1997) predates all of this.
The authorization draft is tracked in (IETF, 2025a), while its threat model
appears in (IETF, 2025b). Anthropic (2024) documents the protocol itself.
A separate survey (Hou et al., 2025) covers the wider ecosystem.
See (Table 3, 2024) for the breakdown, and the figure (Accessed: 1 May 2026).
An orphan citation appears here (Nonexistent, 2019).

## References

Anthropic (2024) 'Model Context Protocol specification'. Available at: https://modelcontextprotocol.io/specification (Accessed: 3 June 2026).

Bradner, S. (1997) 'Key words for use in RFCs to Indicate Requirement Levels', RFC 2119. Available at: https://www.rfc-editor.org/rfc/rfc2119.

Debenedetti, E., Zhang, J. and Carlini, N. (2024) 'AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents', arXiv:2406.13352.

Greshake, K., Abdelnabi, S. and Mishra, S. (2023) 'Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection', Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security. doi:10.1145/3605764.3623985.

Hou, X., Zhao, Y. and Wang, S. (2025) 'Model Context Protocol (MCP): Landscape, Security Threats, and Future Research Directions', arXiv:2503.23278.

IETF (2025a) 'The OAuth 2.1 Authorization Framework', Internet-Draft draft-ietf-oauth-v2-1-13. Available at: https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/.

IETF (2025b) 'OAuth 2.0 Security Best Current Practice', Internet-Draft draft-ietf-oauth-security-topics-29.

Uncited, A. (2021) 'A paper that nobody in this document cites', Journal of Irreproducible Results. doi:10.1000/uncited.
