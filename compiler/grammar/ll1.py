from grammar.first_follow import compute_first, compute_follow

# ============================================================
# LEFT RECURSION DETECTION
# ============================================================

def check_left_recursion(grammar):
    """
    Returns list of dicts describing each left-recursive production.
    E.g. E → E + T is left-recursive because first symbol == E itself.
    """
    issues = []

    for nt, productions in grammar.items():
        for prod in productions:
            if prod and prod[0] == nt:
                issues.append({
                    "non_terminal": nt,
                    "production": prod,
                    "message": f"Left recursion detected: {nt} → {' '.join(prod)}"
                })

    return issues

# ============================================================
# LEFT RECURSION REMOVAL
# ============================================================

def remove_left_recursion(grammar):
    """
    Removes immediate left recursion from all non-terminals.

    E → E + T | T
    becomes:
    E  → T E'
    E' → + T E' | ε
    """
    new_grammar = {}

    for nt, productions in grammar.items():
        recursive     = [p for p in productions if p and p[0] == nt]
        non_recursive = [p for p in productions if not p or p[0] != nt]

        if not recursive:
            # No left recursion — keep as-is
            new_grammar[nt] = productions
        else:
            prime = nt + "'"

            # E → β E'  for each non-recursive β
            new_grammar[nt] = [b + [prime] for b in non_recursive]

            # E' → α E' | ε  for each recursive α (strip leading nt)
            new_grammar[prime] = [a[1:] + [prime] for a in recursive] + [['ε']]

    return new_grammar


# ============================================================
# LEFT FACTORING
# ============================================================

def left_factor(grammar):
    """
    Removes common prefixes from productions.

    A → a B | a C
    becomes:
    A  → a A'
    A' → B | C
    """
    new_grammar = {}

    for nt, productions in grammar.items():
        # Group productions by first symbol
        prefix_map = {}

        for prod in productions:
            first_sym = prod[0] if prod else 'ε'
            prefix_map.setdefault(first_sym, []).append(prod)

        factored = []
        extras = {}

        for prefix, prods in prefix_map.items():
            if len(prods) == 1:
                # No common prefix — keep as-is
                factored.append(prods[0])
            else:
                # Factor out common prefix
                prime = nt + "'"
                # Avoid name collision
                while prime in grammar or prime in extras:
                    prime += "'"

                factored.append([prefix, prime])

                # Remainders after stripping prefix
                remainders = []
                for p in prods:
                    rest = p[1:]
                    remainders.append(rest if rest else ['ε'])

                extras[prime] = remainders

        new_grammar[nt] = factored
        new_grammar.update(extras)

    return new_grammar


# ============================================================
# FIRST OF STRING  (helper)
# ============================================================

def compute_first_of_string(production, first, grammar):
    """
    Computes FIRST set of a production (list of symbols).
    """
    result = set()

    for symbol in production:
        if symbol not in grammar:
            # Terminal
            result.add(symbol)
            return result

        result |= (first[symbol] - {'ε'})

        if 'ε' not in first[symbol]:
            return result

    # All symbols can derive ε
    result.add('ε')
    return result


# ============================================================
# LL(1) TABLE BUILDER
# ============================================================

def build_ll1_table(grammar, first, follow):
    """
    Builds the LL(1) predictive parsing table.
    Keys are tuples: (NonTerminal, terminal)
    """
    table = {}
    conflicts = []

    for head in grammar:
        for production in grammar[head]:

            first_set = compute_first_of_string(production, first, grammar)

            # Fill using FIRST set
            for terminal in first_set - {'ε'}:
                key = (head, terminal)

                if key in table and table[key] != production:
                    conflicts.append({
                        "non_terminal": head,
                        "terminal": terminal,
                        "conflict": "LL(1) conflict",
                        "existing": table[key],
                        "new": production
                    })
                else:
                    table[key] = production

            # If ε in FIRST → fill using FOLLOW
            if 'ε' in first_set:
                for terminal in follow[head]:
                    key = (head, terminal)

                    if key in table and table[key] != production:
                        conflicts.append({
                            "non_terminal": head,
                            "terminal": terminal,
                            "conflict": "LL(1) conflict",
                            "existing": table[key],
                            "new": production
                        })
                    else:
                        table[key] = production

    return table, conflicts


# ============================================================
# FULL LL(1) PIPELINE
# ============================================================

def run_ll1_pipeline(grammar):
    """
    Full pipeline:
    1. Check left recursion → warn + fix
    2. Check left factoring → fix
    3. Compute FIRST & FOLLOW
    4. Build LL(1) table
    
    Returns a result dict with warnings, final grammar, and table.
    """
    result = {
        "warnings": [],
        "grammar_modified": False,
        "original_grammar": grammar,
        "final_grammar": grammar,
        "first": {},
        "follow": {},
        "table": {},
        "conflicts": []
    }

    # ── Step 1: Left recursion ──────────────────────────────
    lr_issues = check_left_recursion(grammar)

    if lr_issues:
        for issue in lr_issues:
            result["warnings"].append(f"⚠ {issue['message']}")

        result["warnings"].append("✔ Auto-correcting: removing left recursion...")
        grammar = remove_left_recursion(grammar)
        result["grammar_modified"] = True
        result["warnings"].append("✔ Left recursion removed successfully.")

    # ── Step 2: Left factoring ──────────────────────────────
    factored = left_factor(grammar)
    if factored != grammar:
        result["warnings"].append("⚠ Common prefixes detected.")
        result["warnings"].append("✔ Auto-correcting: applying left factoring...")
        grammar = factored
        result["grammar_modified"] = True
        result["warnings"].append("✔ Left factoring applied successfully.")

    result["final_grammar"] = grammar

    # ── Step 3: FIRST & FOLLOW ──────────────────────────────
    start_symbol = list(grammar.keys())[0]
    first  = compute_first(grammar)
    follow = compute_follow(grammar, first, start_symbol)

    result["first"]  = {k: list(v) for k, v in first.items()}
    result["follow"] = {k: list(v) for k, v in follow.items()}

    # ── Step 4: Build LL(1) table ───────────────────────────
    table, conflicts = build_ll1_table(grammar, first, follow)

    # ✅ Convert tuple keys to strings for JSON serialization
    result["table"]     = {f"{k[0]},{k[1]}": v for k, v in table.items()}
    result["conflicts"] = conflicts

    if conflicts:
        result["warnings"].append(f"⚠ {len(conflicts)} LL(1) conflict(s) found — grammar may not be LL(1).")
    else:
        result["warnings"].append("✔ LL(1) table built successfully. No conflicts.")

    return result
