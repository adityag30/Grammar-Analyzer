# ============================================================
# GRAMMAR PARSER & VALIDATOR
# Parses raw text grammar input into structured dict
# ============================================================


def parse_grammar(grammar_text):
    """
    Parses raw CFG text into a grammar dict.

    Input format:
        E -> E + T | T
        T -> T * F | F
        F -> id | num | ( E )

    Supports:
        - Multiple productions via '|'
        - Epsilon via 'e', 'eps', 'epsilon', or 'ε'
        - Primes in non-terminal names e.g. E'
    """
    grammar = {}

    lines = grammar_text.strip().split("\n")

    for line_no, line in enumerate(lines, start=1):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue

        # Validate arrow
        if "->" not in line:
            raise ValueError(
                f"Line {line_no}: Missing '->'. "
                f"Expected format: 'A -> B C | D'"
            )

        left, right = line.split("->", 1)
        left = left.strip()

        # Validate LHS — allow letters, digits, primes (E', T'')
        if not left:
            raise ValueError(f"Line {line_no}: Empty left-hand side.")

        # ✅ Allow primes in non-terminal names like E', T''
        if not all(c.isalnum() or c == "'" or c == '_' for c in left):
            raise ValueError(
                f"Line {line_no}: Invalid non-terminal name '{left}'. "
                f"Only letters, digits, underscores, and primes (') allowed."
            )

        right_parts = right.split("|")

        if left not in grammar:
            grammar[left] = []

        for part in right_parts:
            symbols = part.strip().split()

            # ✅ Normalize all epsilon representations
            if not symbols or symbols in [['e'], ['eps'], ['epsilon'], ['ε']]:
                symbols = ['ε']

            grammar[left].append(symbols)

    return grammar


# ============================================================
# TERMINALS & NON-TERMINALS EXTRACTOR
# ============================================================

def get_terminals_nonterminals(grammar):
    """
    Returns (terminals, non_terminals) sets from a grammar dict.
    Terminals are any symbol that is not a non-terminal and not ε.
    """
    non_terminals = set(grammar.keys())
    terminals = set()

    for productions in grammar.values():
        for production in productions:
            for symbol in production:
                if symbol not in non_terminals and symbol != 'ε':
                    terminals.add(symbol)

    return terminals, non_terminals


# ============================================================
# GRAMMAR VALIDATOR
# ============================================================

def validate_grammar(grammar):
    """
    Validates a grammar dict for common issues.
    Returns list of error strings (empty = valid).
    """
    errors = []
    non_terminals = set(grammar.keys())

    for head, productions in grammar.items():

        # ✅ Allow primes in non-terminal names like E'
        if not all(c.isalnum() or c == "'" or c == '_' for c in head):
            errors.append(
                f"Invalid non-terminal name: '{head}'. "
                f"Only letters, digits, underscores, primes allowed."
            )

        if not productions:
            errors.append(f"Non-terminal '{head}' has no productions.")

        for prod in productions:
            if not prod:
                errors.append(f"Empty production found in '{head}'.")
                continue

            # ✅ Check for undefined non-terminals on RHS
            for symbol in prod:
                if (
                    symbol != 'ε'
                    and symbol.isupper()          # likely a non-terminal
                    and symbol not in non_terminals
                ):
                    errors.append(
                        f"Undefined non-terminal '{symbol}' used in "
                        f"'{head} → {' '.join(prod)}'."
                    )

    return errors


# ============================================================
# GRAMMAR FORMATTER  (for display)
# ============================================================

def format_grammar(grammar):
    """
    Converts grammar dict back to readable string.

    E → E + T | T
    T → T * F | F
    F → id | num | ( E )
    """
    lines = []

    for head, productions in grammar.items():
        rhs = " | ".join(" ".join(prod) for prod in productions)
        lines.append(f"{head} → {rhs}")

    return "\n".join(lines)