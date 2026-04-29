import re

TOKEN_RE = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([A-Za-z_]\w*)|(.))")

# ============================================================
# TOKENIZER
# ============================================================

def tokenize(input_string):
    """
    Returns list of (token_type, value) tuples.
    token_type: 'num', 'id', or the operator itself
    """
    tokens = []
    for m in TOKEN_RE.finditer(input_string):
        num, ident, other = m.groups()
        if num:
            tokens.append(('num', num))
        elif ident:
            tokens.append(('id', ident))
        elif other and other.strip():
            tokens.append((other, other))
    return tokens


def normalize_tokens(input_string):
    """
    Returns list of token type strings only.
    e.g. 'a + b * 2' → ['id', '+', 'id', '*', 'num']
    """
    return [t[0] for t in tokenize(input_string)]


def repair_input_string(input_string):
    """
    Repairs common invalid operator sequences by inserting placeholder
    operands ('id') where they are missing.
    """
    tokens = tokenize(input_string)
    corrected = []

    def is_operator_token(ttype):
        return ttype not in ('id', 'num', '(', ')')

    for i, (ttype, value) in enumerate(tokens):
        prev_type = corrected[-1][0] if corrected else None
        next_type = tokens[i + 1][0] if i + 1 < len(tokens) else None

        if is_operator_token(ttype):
            # unary + or - are allowed at start or after another operator or '('
            is_unary = (
                ttype in ('+', '-') and
                (prev_type is None or prev_type == '(' or is_operator_token(prev_type)) and
                next_type in ('id', 'num', '(')
            )

            if not is_unary and (prev_type is None or prev_type == '(' or is_operator_token(prev_type)):
                corrected.append(('id', 'id'))

            corrected.append((ttype, value))

            if not is_unary and (next_type is None or next_type == '(' or is_operator_token(next_type)):
                corrected.append(('id', 'id'))
        else:
            corrected.append((ttype, value))

    return ''.join(value for _, value in corrected)


# ============================================================
# GRAMMAR GENERATOR
# ============================================================

def generate_grammar(input_string):
    """
    Automatically generates a CFG from an input string.
    Detects operators and builds appropriate grammar.
    """
    tokens = normalize_tokens(input_string)

    if not tokens:
        return {
            "grammar": {},
            "warnings": ["⚠ Empty input. No grammar generated."]
        }

    warnings = []

    # ✅ Exclude id, num, parens, AND = from operators list
    operators = [
        t for t in tokens
        if t not in ('id', 'num', '(', ')', '=')
    ]
    operators = list(dict.fromkeys(operators))  # deduplicate, preserve order

    grammar = build_expression_grammar(operators, warnings)

    # ✅ Assignment: id = E, not E = E
    if '=' in tokens:
        grammar['S'] = [['id', '=', 'E'], ['E']]
        warnings.append("✔ Assignment pattern detected. Added S → id = E | E")

    return {
        "grammar": grammar,
        "warnings": warnings
    }


# ============================================================
# GRAMMAR BUILDER
# ============================================================

def build_expression_grammar(operators, warnings=None):
    """
    Builds a left-recursive CFG based on detected operators.
    Left recursion is intentional here — ll1.py pipeline will
    detect and remove it automatically.

    Precedence (low to high):
        + -   →  E level
        * /   →  T level
        ^     →  F level (right-associative)
    """
    if warnings is None:
        warnings = []

    grammar = {}

    low_ops  = [op for op in ['+', '-'] if op in operators]
    med_ops  = [op for op in ['*', '/'] if op in operators]
    has_pow  = '^' in operators

    # ── Highest precedence: ^ ───────────────────────────────
    if has_pow:
        # P is the atom level
        grammar['P'] = [['id'], ['num'], ['(', 'E', ')']]
        # ✅ Right-associative, no left recursion: F → P ^ F | P
        grammar['F'] = [['P', '^', 'F'], ['P']]
        warnings.append("✔ Power operator detected. Using right-associative F → P ^ F | P")
    else:
        grammar['F'] = [['id'], ['num'], ['(', 'E', ')']]

    # ── Medium precedence: * / ──────────────────────────────
    grammar['T'] = [['F']]
    for op in med_ops:
        # Left-recursive: T → T * F  (will be fixed by pipeline)
        grammar['T'].append(['T', op, 'F'])

    # ── Low precedence: + - ─────────────────────────────────
    grammar['E'] = [['T']]
    for op in low_ops:
        # Left-recursive: E → E + T  (will be fixed by pipeline)
        grammar['E'].append(['E', op, 'T'])

    # ── Unknown operators → lowest precedence ───────────────
    known_ops = ['+', '-', '*', '/', '^']
    other_ops = [op for op in operators if op not in known_ops]

    for op in other_ops:
        grammar['E'].append(['E', op, 'T'])
        warnings.append(f"⚠ Unknown operator '{op}' added at lowest precedence (E level).")

    # ── Warn about left recursion ────────────────────────────
    has_lr = any(
        prod and prod[0] == nt
        for nt, productions in grammar.items()
        for prod in productions
    )
    if has_lr:
        warnings.append(
            "⚠ Generated grammar contains left recursion. "
            "LL(1) pipeline will auto-correct this."
        )

    return grammar


# ============================================================
# UNARY OPERATOR SUPPORT
# ============================================================

def detect_unary(input_string):
    """
    Detects if input has unary operators like -a or !flag.
    Returns list of unary operators found.
    """
    tokens = tokenize(input_string)
    unary_ops = []

    for i, (ttype, tval) in enumerate(tokens):
        if ttype in ('-', '!', '~'):
            # Unary if at start or after another operator or '('
            if i == 0 or tokens[i-1][0] in ('(', '+', '-', '*', '/', '^', '='):
                unary_ops.append(tval)

    return list(set(unary_ops))


def add_unary_support(grammar, unary_ops, warnings):
    """
    Extends grammar to handle unary operators.
    e.g. -a becomes: F → - F | id | num | (E)
    """
    if not unary_ops:
        return grammar

    base_f = grammar.get('F', [['id'], ['num'], ['(', 'E', ')']])

    for op in unary_ops:
        base_f.append([op, 'F'])
        warnings.append(f"✔ Unary operator '{op}' detected. Added F → {op} F")

    grammar['F'] = base_f
    return grammar