"""Checks shared by the verifiers. Pure functions of their arguments."""


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def constraint(identifier, text, ok, expected=None, actual=None):
    return {"id": identifier, "constraint": text, "ok": ok, "expected": expected, "actual": actual}


def failed(constraints):
    return [item for item in constraints if not item["ok"]]
