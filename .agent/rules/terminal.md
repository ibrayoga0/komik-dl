# Terminal Inspection

Terminal inspection is a fallback.

Prefer Analyze whenever possible.

Only use terminal commands when:
- Analyze is unavailable.
- Raw file contents are required.
- Exact text verification is required.
- Binary or generated files require manual inspection.

Avoid relying on:
- head
- tail
- Select-Object
- Get-Content with line limits
- sed with partial ranges
- any command that only reads part of a file

If terminal inspection is required, continue until the complete relevant content has been inspected.

Never make implementation decisions from partial terminal output.