# ============================================================
# FIRST & FOLLOW SET COMPUTATION
# ============================================================


def compute_first(grammar):
    """
    Computes FIRST sets for all non-terminals in the grammar.

    FIRST(A) = set of terminals that can begin any string
               derived from A, plus ε if A can derive empty.
    """
    first = {nt: set() for nt in grammar}

    changed = True
    while changed:
        changed = False

        for head, productions in grammar.items():
            for production in productions:

                # ✅ Epsilon production
                if production == ['ε']:
                    if 'ε' not in first[head]:
                        first[head].add('ε')
                        changed = True
                    continue

                for symbol in production:

                    # Terminal — add directly
                    if symbol not in grammar:
                        if symbol not in first[head]:
                            first[head].add(symbol)
                            changed = True
                        break

                    # Non-terminal — add its FIRST (minus ε)
                    before = len(first[head])
                    first[head] |= (first[symbol] - {'ε'})

                    if len(first[head]) != before:
                        changed = True

                    # Only continue if ε ∈ FIRST(symbol)
                    if 'ε' not in first[symbol]:
                        break

                else:
                    # ✅ All symbols in production can derive ε
                    if 'ε' not in first[head]:
                        first[head].add('ε')
                        changed = True

    return first


def compute_follow(grammar, first, start_symbol):
    """
    Computes FOLLOW sets for all non-terminals in the grammar.

    FOLLOW(A) = set of terminals that can appear immediately
                to the right of A in some sentential form.
    Always includes '$' for the start symbol.
    """
    follow = {nt: set() for nt in grammar}
    follow[start_symbol].add('$')

    changed = True
    while changed:
        changed = False

        for head, productions in grammar.items():
            for production in productions:
                for i, symbol in enumerate(production):

                    # Only care about non-terminals
                    if symbol not in grammar:
                        continue

                    rest = production[i + 1:]

                    # ✅ Compute FIRST of the rest of production
                    first_of_rest = set()
                    rest_can_derive_epsilon = True

                    for sym in rest:
                        if sym not in grammar:
                            # Terminal
                            first_of_rest.add(sym)
                            rest_can_derive_epsilon = False
                            break
                        else:
                            first_of_rest |= (first[sym] - {'ε'})
                            if 'ε' not in first[sym]:
                                rest_can_derive_epsilon = False
                                break
                    # If rest is empty, rest_can_derive_epsilon stays True

                    # Add FIRST(rest) - {ε} to FOLLOW(symbol)
                    before = len(follow[symbol])
                    follow[symbol] |= first_of_rest

                    # ✅ If rest can derive ε (or is empty),
                    #    add FOLLOW(head) to FOLLOW(symbol)
                    if rest_can_derive_epsilon:
                        follow[symbol] |= follow[head]

                    if len(follow[symbol]) != before:
                        changed = True

    return follow


# ============================================================
# HELPER — FIRST of an arbitrary string
# ============================================================

def first_of_string(symbols, first, grammar):
    """
    Computes FIRST set of an arbitrary list of symbols.
    Useful for LL(1) table construction.
    """
    result = set()

    for sym in symbols:
        if sym not in grammar:
            result.add(sym)
            return result

        result |= (first[sym] - {'ε'})

        if 'ε' not in first[sym]:
            return result

    # All symbols can derive ε
    result.add('ε')
    return result