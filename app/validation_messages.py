"""Mesajele de validare în română, pentru erorile de tip 400.

Pydantic descrie fiecare problemă printr-un tip (de exemplu `missing` sau
`string_too_short`) și un mesaj în engleză. Aici alegem mesajul în română
după tip, cu valorile din `ctx` (limita minimă, lista de valori permise).
"""

from typing import Any


def count_with_noun(count: int, singular: str, plural: str) -> str:
    """Scrie numărul cu substantivul potrivit: 1 caracter, 5 caractere, 20 de."""
    if count == 1:
        return f"1 {singular}"
    # În română, de la 20 în sus (cu excepții ca 101-119) se adaugă „de”.
    if count >= 20 and (count % 100 >= 20 or count % 100 == 0):
        return f"{count} de {plural}"
    return f"{count} {plural}"


def describe_choices(expected: str) -> str:
    """Transformă „'a', 'b' or 'c'” (lista lui Pydantic) în „'a', 'b' sau 'c'”."""
    return expected.replace(" or ", " sau ")


def translate_message(error: dict[str, Any]) -> str:
    """Întoarce mesajul în română pentru o eroare de validare Pydantic."""
    error_type = error["type"]
    ctx = error.get("ctx") or {}

    if error_type == "missing":
        return "câmpul este obligatoriu"
    if error_type == "string_too_short":
        length = count_with_noun(ctx["min_length"], "caracter", "caractere")
        return f"textul trebuie să aibă cel puțin {length}"
    if error_type == "string_too_long":
        length = count_with_noun(ctx["max_length"], "caracter", "caractere")
        return f"textul poate avea cel mult {length}"
    if error_type == "greater_than_equal":
        return f"valoarea trebuie să fie cel puțin {ctx['ge']}"
    if error_type == "less_than_equal":
        return f"valoarea poate fi cel mult {ctx['le']}"
    if error_type == "greater_than":
        return f"valoarea trebuie să fie mai mare decât {ctx['gt']}"
    if error_type == "less_than":
        return f"valoarea trebuie să fie mai mică decât {ctx['lt']}"
    if error_type in ("int_type", "int_parsing", "int_from_float"):
        return "valoarea trebuie să fie un număr întreg"
    if error_type in ("float_type", "float_parsing"):
        return "valoarea trebuie să fie un număr"
    if error_type == "string_type":
        return "valoarea trebuie să fie text"
    if error_type in ("bool_type", "bool_parsing"):
        return "valoarea trebuie să fie true sau false"
    if error_type == "literal_error":
        return f"valoarea trebuie să fie una dintre {describe_choices(ctx['expected'])}"
    if error_type.startswith("date"):
        return "data trebuie să fie în formatul AAAA-LL-ZZ"
    if error_type.startswith("time"):
        return "ora trebuie să fie în formatul HH:MM"
    if error_type == "json_invalid":
        return "corpul cererii nu este un JSON valid"
    if error_type in ("model_type", "model_attributes_type", "dict_type"):
        return "corpul cererii trebuie să fie un obiect JSON"
    if error_type == "list_type":
        return "valoarea trebuie să fie o listă"
    if error_type == "extra_forbidden":
        return "câmpul nu este permis"
    if error_type == "value_error":
        # EmailStr dă un mesaj în engleză, cu motivul în `ctx["reason"]`.
        if error.get("msg", "").startswith("value is not a valid email address"):
            return "adresa de email nu este validă"
        # Celelalte mesaje sunt scrise de noi (ValueError din validatori).
        message = str(ctx.get("error", ""))
        if message:
            return message
    # Un tip neprevăzut primește un mesaj general, tot în română.
    return "valoare invalidă"


def field_name(location: tuple[Any, ...]) -> str:
    """Numele câmpului, așa cum îl vede clientul API.

    `location` începe cu sursa (`body`, `query`, `path`). Parametrii din adresă
    au în cod nume ca `facility_id`, dar în specificație apar ca `{id}`.
    """
    parts = [str(part) for part in location[1:]]
    if location and location[0] == "path" and parts and parts[-1].endswith("_id"):
        parts[-1] = "id"
    return ".".join(parts)


def describe_errors(errors: list[dict[str, Any]]) -> str:
    """Mesajul complet trimis clientului: „Date invalide. câmp: problemă; ...”."""
    problems = []
    for error in errors:
        name = field_name(tuple(error["loc"]))
        message = translate_message(error)
        problems.append(f"{name}: {message}" if name else message)
    return "Date invalide. " + "; ".join(problems)
