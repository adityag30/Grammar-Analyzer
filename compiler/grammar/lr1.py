from copy import deepcopy


def augment_grammar(grammar):
    """
    Adds S' -> S at the BEGINNING so it's always treated as start.
    """
    start = list(grammar.keys())[0]
    new_start = start + "'"
    
    # ✅ New start must be FIRST key
    new_grammar = {new_start: [[start]]}
    new_grammar.update(deepcopy(grammar))
    
    return new_grammar, new_start


def first_of_string(symbols, first, grammar):
    """
    Computes FIRST of a string of symbols.
    Used for lookahead computation in closure.
    """
    result = set()

    for sym in symbols:
        if sym not in grammar:
            # Terminal
            result.add(sym)
            return result

        result |= (first[sym] - {'ε'})

        if 'ε' not in first[sym]:
            return result

    # All symbols derived ε
    result.add('ε')
    return result


def closure(items, grammar, first):
    """
    Computes LR(1) closure of a set of items.
    Item format: (head, body_tuple, dot_position, lookahead)
    """
    closure_set = set(items)

    while True:
        new_items = set()

        for (head, body, dot, lookahead) in closure_set:
            if dot >= len(body):
                continue

            B = body[dot]

            if B not in grammar:
                continue  # terminal, skip

            # β is everything after B, plus the lookahead
            beta = list(body[dot + 1:]) + [lookahead]
            lookaheads = first_of_string(beta, first, grammar)

            for prod in grammar[B]:
                # ✅ Handle epsilon productions properly
                body_tuple = tuple(prod) if prod != ['ε'] else ('ε',)
                for la in lookaheads:
                    new_items.add((B, body_tuple, 0, la))

        if new_items.issubset(closure_set):
            break

        closure_set |= new_items

    return frozenset(closure_set)


def goto(items, symbol, grammar, first):
    """
    Computes goto(items, symbol) — move dot past symbol, then closure.
    """
    moved = set()

    for (head, body, dot, lookahead) in items:
        if dot < len(body) and body[dot] == symbol:
            moved.add((head, body, dot + 1, lookahead))

    if not moved:
        return frozenset()

    return closure(moved, grammar, first)


def build_lr1_states(grammar, first):
    """
    Builds the canonical LR(1) collection of item sets.
    Returns: states list, transitions dict, new_start symbol, augmented grammar
    """
    aug_grammar, new_start = augment_grammar(grammar)

    # ✅ Start item uses augmented start
    start_prod = aug_grammar[new_start][0]
    start_item = (new_start, tuple(start_prod), 0, '$')

    states = [closure({start_item}, aug_grammar, first)]
    transitions = {}

    i = 0
    # ✅ Use index-based loop so we handle growing list correctly
    while i < len(states):
        state = states[i]

        # Collect all symbols after dots
        symbols = set()
        for (head, body, dot, _) in state:
            if dot < len(body):
                symbols.add(body[dot])

        for symbol in symbols:
            new_state = goto(state, symbol, aug_grammar, first)

            if not new_state:
                continue

            if new_state not in states:
                states.append(new_state)

            transitions[(i, symbol)] = states.index(new_state)

        i += 1

    return states, transitions, new_start, aug_grammar


def build_lr1_table(states, transitions, grammar, start):
    """
    Builds ACTION and GOTO tables from LR(1) states.
    All keys are tuples: (state_int, symbol_str)
    """
    action = {}
    goto_table = {}
    conflicts = []

    for i, state in enumerate(states):
        for (head, body, dot, lookahead) in state:

            # SHIFT — dot is before a terminal
            if dot < len(body):
                symbol = body[dot]

                if symbol not in grammar:  # it's a terminal
                    key = (i, symbol)
                    value = ("shift", transitions[(i, symbol)])

                    if key in action and action[key] != value:
                        conflicts.append({
                            "state": i,
                            "symbol": symbol,
                            "conflict": "shift-reduce" if action[key][0] == "reduce" else "shift-shift",
                            "existing": action[key],
                            "new": value
                        })
                    else:
                        action[key] = value

            # REDUCE or ACCEPT — dot is at end
            else:
                if head == start:
                    # ✅ Accept
                    action[(i, '$')] = ("accept",)

                else:
                    key = (i, lookahead)
                    value = ("reduce", head, list(body))

                    if key in action and action[key] != value:
                        conflicts.append({
                            "state": i,
                            "symbol": lookahead,
                            "conflict": "reduce-reduce" if action[key][0] == "reduce" else "shift-reduce",
                            "existing": action[key],
                            "new": value
                        })
                    else:
                        action[key] = value

        # GOTO — for non-terminals
        for nt in grammar:
            if (i, nt) in transitions:
                goto_table[(i, nt)] = transitions[(i, nt)]

    return action, goto_table, conflicts