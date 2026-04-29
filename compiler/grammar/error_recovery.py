# ============================================================
# ERROR RECOVERY MODULE
# Supports both LL(1) and LR(1) parsers
# ============================================================


# ============================================================
# PANIC MODE — LL(1)
# ============================================================

def panic_mode_ll1(stack, input_buffer, follow, grammar):
    """
    Panic mode recovery for LL(1).
    
    Strategy:
    - Pop stack until we find a non-terminal whose FOLLOW set
      contains the current input symbol.
    - Skip input tokens until we find a sync token (FOLLOW sets).
    
    Returns: stack, input_buffer, log of actions taken
    """
    log = []

    # Build sync set from FOLLOW sets of all non-terminals on stack
    sync_tokens = set()
    for sym in stack:
        if sym in follow:
            sync_tokens |= follow[sym]
    sync_tokens.add('$')

    log.append(f"⚠ Error detected. Sync tokens: {sorted(sync_tokens)}")

    # ── Phase 1: Skip input until sync token ────────────────
    skipped_input = []
    while input_buffer and input_buffer[0] not in sync_tokens:
        skipped_input.append(input_buffer.pop(0))

    if skipped_input:
        log.append(f"✔ Skipped input tokens: {skipped_input}")

    if not input_buffer:
        log.append("✘ Reached end of input during panic recovery.")
        return stack, input_buffer, log

    current = input_buffer[0]

    # ── Phase 2: Pop stack until non-terminal with current in FOLLOW ──
    popped_stack = []
    while stack and stack[-1] != '$':
        top = stack[-1]

        if top in follow and current in follow[top]:
            log.append(f"✔ Resumed at non-terminal '{top}' with input '{current}'")
            break

        popped_stack.append(stack.pop())

    if popped_stack:
        log.append(f"✔ Popped stack symbols: {popped_stack}")

    return stack, input_buffer, log


# ============================================================
# PANIC MODE — LR(1)
# ============================================================

def panic_mode_lr1(stack, input_buffer, action, goto_table, grammar):
    """
    Panic mode recovery for LR(1).

    Strategy:
    - Pop states from stack until a state is found that has
      a GOTO entry for some non-terminal.
    - Skip input until a token valid in that state is found.

    Returns: stack, input_buffer, log of actions taken
    """
    log = []
    log.append("⚠ Error detected in LR(1) parser. Starting panic recovery...")

    # Collect all terminals that appear in action table
    valid_terminals = set(sym for (_, sym) in action.keys())
    valid_terminals.add('$')

    # ── Phase 1: Pop stack until a useful state ──────────────
    popped = []
    while len(stack) > 1:
        state = stack[-1]

        # Check if this state has any action entries
        has_action = any(s == state for (s, _) in action.keys())

        if has_action:
            log.append(f"✔ Found recoverable state: {state}")
            break

        popped.append(stack.pop())

    if popped:
        log.append(f"✔ Popped states from stack: {popped}")

    # ── Phase 2: Skip input until valid token ───────────────
    state = stack[-1]
    valid_here = {sym for (s, sym) in action.keys() if s == state}
    valid_here.add('$')

    skipped = []
    while input_buffer and input_buffer[0] not in valid_here:
        skipped.append(input_buffer.pop(0))

    if skipped:
        log.append(f"✔ Skipped input tokens: {skipped}")

    if not input_buffer:
        log.append("✘ Reached end of input during panic recovery.")

    return stack, input_buffer, log


# ============================================================
# PHRASE LEVEL RECOVERY — LR(1)
# ============================================================

def phrase_level_recovery_lr1(stack, input_buffer, action, goto_table, grammar):
    """
    Phrase-level recovery for LR(1).

    Strategies tried in order:
    1. Delete current input token (it's unexpected)
    2. Insert a missing token (if state has only one valid action)
    3. Replace current token with expected one

    Returns: stack, input_buffer, log
    """
    log = []

    if not input_buffer or not stack:
        return stack, input_buffer, log

    state = stack[-1]
    current = input_buffer[0]

    valid_inputs = {sym for (s, sym) in action.keys() if s == state}

    # ── Strategy 1: Delete unexpected input token ────────────
    if current not in valid_inputs and current != '$':
        removed = input_buffer.pop(0)
        log.append(f"✔ Phrase-level: Deleted unexpected token '{removed}'")
        return stack, input_buffer, log

    # ── Strategy 2: Insert missing token ─────────────────────
    if len(valid_inputs) == 1:
        insert = list(valid_inputs)[0]
        input_buffer.insert(0, insert)
        log.append(f"✔ Phrase-level: Inserted missing token '{insert}'")
        return stack, input_buffer, log

    # ── Strategy 3: Replace with valid token ────────────────
    if valid_inputs:
        replacement = next(iter(valid_inputs))
        old = input_buffer.pop(0) if input_buffer else None
        input_buffer.insert(0, replacement)
        log.append(
            f"✔ Phrase-level: Replaced '{old}' with '{replacement}' "
            f"(valid for state {state})"
        )
        return stack, input_buffer, log

    # ── Fallback: pop stack ───────────────────────────────────
    popped = stack.pop()
    log.append(f"✔ Phrase-level fallback: Popped state '{popped}' from stack")

    return stack, input_buffer, log


# ============================================================
# PHRASE LEVEL RECOVERY — LL(1)
# ============================================================

def phrase_level_recovery_ll1(stack, input_buffer, table, follow, grammar):
    """
    Phrase-level recovery for LL(1).

    Strategies tried in order:
    1. Delete current input token (it's unexpected)
    2. Insert a missing token (if stack top has only one valid option)
    3. Replace current token with expected one

    Returns: stack, input_buffer, log
    """
    log = []

    if not input_buffer or not stack:
        return stack, input_buffer, log

    top = stack[-1]
    current = input_buffer[0]

    if top in grammar:
        valid_inputs = {sym for (nt, sym) in table.keys() if nt == top}

        # ── Strategy 1: Delete unexpected input token ────────────
        if current not in valid_inputs and current != '$':
            removed = input_buffer.pop(0)
            log.append(f"✔ Phrase-level: Deleted unexpected token '{removed}'")
            return stack, input_buffer, log

        # ── Strategy 2: Insert missing token ─────────────────────
        if len(valid_inputs) == 1:
            insert = list(valid_inputs)[0]
            input_buffer.insert(0, insert)
            log.append(f"✔ Phrase-level: Inserted missing token '{insert}'")
            return stack, input_buffer, log

    # ── Strategy 3: Replace with FOLLOW-based token ──────────
    if top in follow and follow[top]:
        replacement = next(iter(follow[top] - {'$'}), None)

        if replacement:
            old = input_buffer.pop(0) if input_buffer else None
            input_buffer.insert(0, replacement)
            log.append(
                f"✔ Phrase-level: Replaced '{old}' with '{replacement}' "
                f"(from FOLLOW({top}))"
            )
            return stack, input_buffer, log

    # ── Fallback: pop stack ───────────────────────────────────
    popped = stack.pop()
    log.append(f"✔ Phrase-level fallback: Popped '{popped}' from stack")

    return stack, input_buffer, log


# ============================================================
# SMART RECOVERY CONTROLLER
# ============================================================

def recover_error(
    parser_type,       # 'll1' or 'lr1'
    stack,
    input_buffer,
    table_or_action,   # LL1: parsing table | LR1: action table
    goto_table,        # LR1 only, pass None for LL1
    follow,            # FOLLOW sets dict
    grammar            # grammar dict
):
    """
    Master recovery controller.
    Decides strategy based on parser type and error context.

    Returns: (strategy_used, stack, input_buffer, log)
    """

    if parser_type == 'll1':
        top = stack[-1] if stack else None
        current = input_buffer[0] if input_buffer else '$'

        # Use phrase-level if top has a valid action nearby
        if top and top in grammar:
            valid = {sym for (nt, sym) in table_or_action.keys() if nt == top}
            if len(valid) <= 3:
                # Few options → phrase level is precise enough
                stack, input_buffer, log = phrase_level_recovery_ll1(
                    stack, input_buffer, table_or_action, follow, grammar
                )
                return "phrase_level", stack, input_buffer, log

        # Default: panic mode
        stack, input_buffer, log = panic_mode_ll1(
            stack, input_buffer, follow, grammar
        )
        return "panic", stack, input_buffer, log

    elif parser_type == 'lr1':
        state = stack[-1] if stack else None
        current = input_buffer[0] if input_buffer else '$'

        # Use phrase-level if state has few valid actions
        if state is not None:
            valid_here = {sym for (s, sym) in table_or_action.keys() if s == state}
            if len(valid_here) <= 3:
                # Few options → phrase level is precise enough
                stack, input_buffer, log = phrase_level_recovery_lr1(
                    stack, input_buffer, table_or_action, goto_table, grammar
                )
                return "phrase_level", stack, input_buffer, log

        # Default: panic mode
        stack, input_buffer, log = panic_mode_lr1(
            stack, input_buffer, table_or_action, goto_table, grammar
        )
        return "panic", stack, input_buffer, log

    else:
        return "none", stack, input_buffer, [f"✘ Unknown parser type: {parser_type}"]