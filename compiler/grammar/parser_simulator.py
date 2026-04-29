from .error_recovery import recover_error

def simulate_ll1(input_tokens, table, start_symbol, follow=None, grammar=None):
    """
    input_tokens: list of token strings e.g. ['id', '+', 'id', '$']
    table: dict with tuple keys (NonTerminal, terminal) -> production
    start_symbol: string e.g. 'E'
    follow: dict of FOLLOW sets (optional, for error recovery)
    grammar: dict of grammar productions (optional, for error recovery)
    """
    stack = ['$', start_symbol]

    if input_tokens[-1] != '$':
        input_tokens = input_tokens + ['$']

    steps = []
    recovery_attempts = 0
    max_recovery = 3

    while True:
        if not stack or not input_tokens:
            steps.append({
                "stack": list(stack),
                "input": list(input_tokens),
                "action": "ERROR: stack or input exhausted"
            })
            return "ERROR", steps

        top = stack[-1]
        current = input_tokens[0]

        steps.append({
            "stack": list(stack),
            "input": list(input_tokens),
            "action": ""
        })

        # ✅ Accept condition
        if top == '$' and current == '$':
            steps[-1]["action"] = "ACCEPT"
            return "ACCEPTED", steps

        # ✅ Terminal match
        if top == current:
            steps[-1]["action"] = f"Match '{top}'"
            stack.pop()
            input_tokens.pop(0)

        # ✅ Apply production rule
        elif (top, current) in table:
            production = table[(top, current)]
            steps[-1]["action"] = f"{top} → {' '.join(production)}"
            stack.pop()

            if production != ['ε']:
                stack.extend(reversed(production))

        # ✅ Error
        else:
            if follow and grammar and recovery_attempts < max_recovery:
                recovery_attempts += 1
                # Attempt error recovery
                strategy, stack, input_tokens, recovery_log = recover_error(
                    'll1', stack, input_tokens, table, None, follow, grammar
                )
                steps[-1]["action"] = f"ERROR: unexpected '{current}' on top '{top}' — {strategy} Recovery: {'; '.join(recovery_log)}"
                # Continue parsing after recovery
            else:
                steps[-1]["action"] = f"ERROR: unexpected '{current}' on top '{top}'"
                return "ERROR", steps


def simulate_lr1(input_tokens, action, goto_table, grammar=None):
    """
    input_tokens: list of token strings e.g. ['id', '+', 'id', '$']
    action: dict with tuple keys (state_int, terminal) -> ('shift', n) | ('reduce', head, body) | ('accept',)
    goto_table: dict with tuple keys (state_int, NonTerminal) -> state_int
    grammar: dict of grammar productions (optional, for error recovery)
    """
    stack = [0]  # only states on stack

    if input_tokens[-1] != '$':
        input_tokens = input_tokens + ['$']

    steps = []
    recovery_attempts = 0
    max_recovery = 3

    while True:
        if not stack or not input_tokens:
            steps.append({
                "stack": list(stack),
                "input": list(input_tokens),
                "action": "ERROR: stack or input exhausted"
            })
            return "ERROR", steps

        state = stack[-1]
        symbol = input_tokens[0]

        # ✅ Tuple key — matches lr1.py exactly
        key = (state, symbol)

        steps.append({
            "stack": list(stack),
            "input": list(input_tokens),
            "action": ""
        })

        # ✅ No action found → error
        if key not in action:
            if grammar and recovery_attempts < max_recovery:
                recovery_attempts += 1
                # Attempt error recovery
                strategy, stack, input_tokens, recovery_log = recover_error(
                    'lr1', stack, input_tokens, action, goto_table, None, grammar
                )
                steps[-1]["action"] = f"ERROR: no action for state {state}, symbol '{symbol}' — {strategy} Recovery: {'; '.join(recovery_log)}"
                # Continue parsing after recovery
            else:
                steps[-1]["action"] = f"ERROR: no action for state {state}, symbol '{symbol}'"
                return "ERROR", steps

        act = action[key]

        # ✅ Accept
        if act[0] == "accept":
            steps[-1]["action"] = "ACCEPT"
            return "ACCEPT", steps

        # ✅ Shift
        elif act[0] == "shift":
            next_state = act[1]
            steps[-1]["action"] = f"Shift → go to state {next_state}"
            stack.append(next_state)
            input_tokens.pop(0)

        # ✅ Reduce
        elif act[0] == "reduce":
            _, head, body = act
            steps[-1]["action"] = f"Reduce {head} → {' '.join(body)}"

            # Pop |body| states (skip ε productions)
            if body != ['ε']:
                for _ in range(len(body)):
                    stack.pop()

            # Goto
            top_state = stack[-1]
            goto_key = (top_state, head)   # ✅ Tuple key — matches lr1.py

            if goto_key not in goto_table:
                steps[-1]["action"] = f"ERROR: no goto for state {top_state}, '{head}'"
                return "ERROR", steps

            stack.append(goto_table[goto_key])