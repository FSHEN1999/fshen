# scenario_1 MeterSphere step 21 loop fix result

## Conclusion

The MeterSphere server was not actually blocked by the `first-credit-model`
request itself. In the latest REG validation, that request returned HTTP 200 in
about 2.2 seconds.

The visible "executing" state came from the following `SUBMITTED` polling loop.
The old loop was risky on MeterSphere because it allowed a long timeout and the
poll counter/status update logic was not guarded tightly enough for server-side
execution.

## Optimized Scene

Target file:

- `D:\data\project\dpu\自动化\scenario_1.ms`

Key optimized behavior now present in the scene:

- The `SUBMITTED` while controller is bounded to `30` polls.
- The loop timeout is reduced from `600000 ms` to `180000 ms`.
- `poll_count` is incremented inside the Groovy while expression.
- Poll status extraction uses `BEANSHELL_JSR233`, which is safer for the
  MeterSphere server than relying on Python script execution in this loop.
- Poll response logging records HTTP status and response body.
- If `SUBMITTED` is not reached, the final script fails explicitly instead of
  leaving the scene looking endlessly "executing".

Current while expression:

```groovy
${__groovy(def raw=vars.get('poll_count'); int c=(raw==null || raw.trim().length()==0) ? 0 : Integer.parseInt(raw); def status=vars.get('credit_offer_status'); boolean keep=!'SUBMITTED'.equals(status) && c < 30; if (keep) { vars.put('poll_count', String.valueOf(c + 1)); }; return keep)}
```

## Validation Update

Target file:

- `D:\data\project\dpu\自动化\validate_scenario_1_direct_flow.py`

The validator now accepts both assertion styles:

- Python: `code != "200"` with `raise Exception`
- BeanShell: `!"200".equals(code)` with `throw new Exception`

This prevents false failures when the `.ms` scene correctly uses BeanShell for
server-side MeterSphere polling.

## Real REG Verification

Command executed through the local REG validation harness:

```powershell
python 自动化\validate_scenario_1_direct_flow.py
```

Latest result file:

- `D:\data\project\dpu\自动化\scenario_1_validation_result.json`

Latest verification result:

- Validation time: `2026-04-27 01:54:26`
- Result: `PASS`
- Phone: `18338109177`
- Merchant ID: `a8bcacbac6304f4eb7fa31f6d3f36673`
- Application ID: `EFA17772259705165455`
- Lender approved offer ID: `lender-EFA17772259705165455`
- Step 21 `first-credit-model`: HTTP 200
- Step 22 `first-application-start`: HTTP 200
- `SUBMITTED` reached after `22` polls
- Final `dpu_credit_offer`: `ACCEPTED`, amount `500000.0`, `e_sign_status=SUCCESS`
- Final lender event count: `4`

## Import Note

The MeterSphere server must import the current
`D:\data\project\dpu\自动化\scenario_1.ms`. If the UI still shows the while
timeout as `600000 ms`, it is still running an older scene export and does not
yet contain this fix.
