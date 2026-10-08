# Rule Guidance

- Every rule must declare examples or typed cases that prove accepted, reported, and fixed behavior as applicable.
- Every fixable rule must pass exact-output, clean-after-fix, and idempotency checks.
- Rules used inside MyBatis or Trellis must declare template safety. Do not infer embedded safety from a hard-coded engine list.
- Preserve strings, comments, quoted identifiers, PostgreSQL casts and dollar quotes, MyBatis parameters, XML entities, and Trellis directives.
- Prefer shared tokenizer/parser helpers over local regular expressions when syntax context matters.
- Regenerate rule documentation after metadata, examples, defaults, or behavior changes.
