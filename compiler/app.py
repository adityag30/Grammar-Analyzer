from flask import Flask, request, jsonify, render_template
from grammar.auto_grammar import generate_grammar, detect_unary, add_unary_support, repair_input_string
from grammar.parser import parse_grammar, get_terminals_nonterminals, validate_grammar, format_grammar
from grammar.first_follow import compute_first, compute_follow
from grammar.ll1 import run_ll1_pipeline
from grammar.lr1 import build_lr1_states, build_lr1_table
from grammar.error_recovery import recover_error
from grammar.parser_simulator import simulate_ll1, simulate_lr1

app = Flask(__name__)


# ============================================================
# HELPER — serialize grammar for JSON
# ============================================================

def serialize_grammar(grammar):
    """
    Converts grammar dict to JSON-safe format.
    Keys are strings, values are lists of lists.
    """
    return {
        head: [prod for prod in productions]
        for head, productions in grammar.items()
    }


def serialize_table(table):
    """
    Converts tuple-keyed table to string-keyed for JSON.
    (NT, terminal) -> "NT,terminal"
    """
    return {
        f"{k[0]},{k[1]}": v
        for k, v in table.items()
    }


# ============================================================
# PAGE ROUTE
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


# ============================================================
# ROUTE 1 — Auto Generate Grammar from Input String
# ============================================================

@app.route('/api/generate-grammar', methods=['POST'])
def api_generate_grammar():
    """
    Input:  { "input_string": "a + b * c" }
    Output: { "grammar": {...}, "warnings": [...], "formatted": "..." }
    """
    data = request.get_json()

    if not data or 'input_string' not in data:
        return jsonify({"error": "Missing 'input_string' in request."}), 400

    input_string = data['input_string'].strip()

    if not input_string:
        return jsonify({"error": "Input string is empty."}), 400

    try:
        corrected_input = repair_input_string(input_string)
        if corrected_input != input_string:
            warnings = [f"✔ Corrected invalid input to '{corrected_input}'"]
            input_string = corrected_input
        else:
            warnings = []

        result = generate_grammar(input_string)
        grammar = result['grammar']
        warnings.extend(result['warnings'])

        # Handle unary operators
        from grammar.auto_grammar import normalize_tokens
        tokens = normalize_tokens(input_string)
        unary_ops = detect_unary(input_string)
        if unary_ops:
            grammar = add_unary_support(grammar, unary_ops, warnings)

        # Validate
        errors = validate_grammar(grammar)
        if errors:
            return jsonify({
                "error": "Grammar validation failed.",
                "details": errors
            }), 422

        response = {
            "grammar": serialize_grammar(grammar),
            "warnings": warnings,
            "formatted": format_grammar(grammar)
        }
        if corrected_input != data['input_string'].strip():
            response["corrected_input"] = corrected_input
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ROUTE 2 — Compute FIRST & FOLLOW Sets
# ============================================================

@app.route('/api/first-follow', methods=['POST'])
def api_first_follow():
    """
    Input:  { "grammar": {...} }
    Output: { "first": {...}, "follow": {...} }
    """
    data = request.get_json()

    if not data or 'grammar' not in data:
        return jsonify({"error": "Missing 'grammar' in request."}), 400

    try:
        grammar = data['grammar']
        start_symbol = list(grammar.keys())[0]

        first  = compute_first(grammar)
        follow = compute_follow(grammar, first, start_symbol)

        return jsonify({
            "first":  {k: sorted(v) for k, v in first.items()},
            "follow": {k: sorted(v) for k, v in follow.items()},
            "start_symbol": start_symbol
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ROUTE 3 — Build LL(1) Table
# ============================================================

@app.route('/api/ll1-table', methods=['POST'])
def api_ll1_table():
    """
    Input:  { "grammar": {...} }
    Output: {
        "warnings": [...],
        "grammar_modified": true/false,
        "original_grammar": {...},
        "final_grammar": {...},
        "first": {...},
        "follow": {...},
        "table": {...},
        "conflicts": [...]
    }
    """
    data = request.get_json()

    if not data or 'grammar' not in data:
        return jsonify({"error": "Missing 'grammar' in request."}), 400

    try:
        grammar = data['grammar']
        result  = run_ll1_pipeline(grammar)

        return jsonify({
            "warnings":         result["warnings"],
            "grammar_modified": result["grammar_modified"],
            "original_grammar": serialize_grammar(result["original_grammar"]),
            "final_grammar":    serialize_grammar(result["final_grammar"]),
            "first":            result["first"],
            "follow":           result["follow"],
            "table":            result["table"],   # already string-keyed in ll1.py
            "conflicts":        result["conflicts"],
            "formatted":        format_grammar(result["final_grammar"])
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ROUTE 4 — Build LR(1) Table
# ============================================================

@app.route('/api/lr1-table', methods=['POST'])
def api_lr1_table():
    """
    Input:  { "grammar": {...} }
    Output: {
        "action": {...},
        "goto": {...},
        "conflicts": [...],
        "states_count": N
    }
    """
    data = request.get_json()

    if not data or 'grammar' not in data:
        return jsonify({"error": "Missing 'grammar' in request."}), 400

    try:
        grammar = data['grammar']

        # Need FIRST sets for LR(1) closure
        first  = compute_first(grammar)
        states, transitions, start, aug_grammar = build_lr1_states(grammar, first)
        action, goto_table, conflicts = build_lr1_table(
            states, transitions, aug_grammar, start
        )

        return jsonify({
            "action":       serialize_table(action),
            "goto":         serialize_table(goto_table),
            "conflicts":    conflicts,
            "states_count": len(states),
            "start_symbol": start
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ROUTE 5 — Simulate LL(1) Parsing
# ============================================================

@app.route('/api/simulate-ll1', methods=['POST'])
def api_simulate_ll1():
    """
    Input:  {
        "input_string": "id + id",
        "grammar": {...}
    }
    Output: {
        "result": "ACCEPTED" | "ERROR",
        "steps": [...],
        "warnings": [...]
    }
    """
    data = request.get_json()

    if not data or 'input_string' not in data or 'grammar' not in data:
        return jsonify({"error": "Missing 'input_string' or 'grammar'."}), 400

    try:
        from grammar.auto_grammar import normalize_tokens
        raw_input = data['input_string'].strip()
        input_string = repair_input_string(raw_input)

        # Correct incomplete expressions
        if input_string and input_string[-1] in '+-*/^%=':
            input_string += ' id'

        grammar      = data['grammar']

        # Run full LL(1) pipeline (handles left recursion etc.)
        pipeline     = run_ll1_pipeline(grammar)
        final_grammar = pipeline["final_grammar"]
        warnings      = pipeline["warnings"]

        # Rebuild first/follow on final grammar
        start_symbol  = list(final_grammar.keys())[0]
        first  = compute_first(final_grammar)
        follow = compute_follow(final_grammar, first, start_symbol)

        # Rebuild table with tuple keys for simulator
        from grammar.ll1 import build_ll1_table
        table, conflicts = build_ll1_table(final_grammar, first, follow)

        # Tokenize corrected input
        input_tokens = normalize_tokens(input_string)

        result, steps = simulate_ll1(input_tokens, table, start_symbol, follow, final_grammar)

        response = {
            "corrected_input": input_string,
            "result":   result,
            "steps":    steps,
            "warnings": warnings,
            "conflicts": conflicts
        }
        if input_string != raw_input:
            response["original_input"] = raw_input
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ROUTE 6 — Simulate LR(1) Parsing
# ============================================================

@app.route('/api/simulate-lr1', methods=['POST'])
def api_simulate_lr1():
    """
    Input:  {
        "input_string": "id + id",
        "grammar": {...}
    }
    Output: {
        "result": "ACCEPT" | "ERROR",
        "steps": [...],
        "conflicts": [...]
    }
    """
    data = request.get_json()

    if not data or 'input_string' not in data or 'grammar' not in data:
        return jsonify({"error": "Missing 'input_string' or 'grammar'."}), 400

    try:
        from grammar.auto_grammar import normalize_tokens
        raw_input = data['input_string'].strip()
        input_string = repair_input_string(raw_input)

        # Correct incomplete expressions
        if input_string and input_string[-1] in '+-*/^%=':
            input_string += ' id'

        grammar      = data['grammar']

        first  = compute_first(grammar)
        states, transitions, start, aug_grammar = build_lr1_states(grammar, first)
        action, goto_table, conflicts = build_lr1_table(
            states, transitions, aug_grammar, start
        )

        input_tokens = normalize_tokens(input_string)
        result, steps = simulate_lr1(input_tokens, action, goto_table, aug_grammar)

        response = {
            "corrected_input": input_string,
            "result":    result,
            "steps":     steps,
            "conflicts": conflicts
        }
        if input_string != raw_input:
            response["original_input"] = raw_input
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ROUTE 7 — Full Pipeline (generate + parse + both tables)
# ============================================================

@app.route('/api/full-pipeline', methods=['POST'])
def api_full_pipeline():
    """
    One-shot route — takes raw input string, runs everything.

    Input:  { "input_string": "a + b * c" }
    Output: {
        "grammar": {...},
        "warnings": [...],
        "first": {...},
        "follow": {...},
        "ll1": { table, conflicts, grammar_modified },
        "lr1": { action, goto, conflicts, states_count }
    }
    """
    data = request.get_json()

    if not data or 'input_string' not in data:
        return jsonify({"error": "Missing 'input_string'."}), 400

    try:
        raw_input = data['input_string'].strip()
        input_string = repair_input_string(raw_input)

        # Correct incomplete expressions by appending 'id' if ends with operator
        if input_string and input_string[-1] in '+-*/^%=':
            input_string += ' id'

        # Step 1 — Generate grammar
        gen_result = generate_grammar(input_string)
        grammar    = gen_result['grammar']
        warnings   = gen_result['warnings']

        # Step 2 — FIRST & FOLLOW
        start_symbol = list(grammar.keys())[0]
        first  = compute_first(grammar)
        follow = compute_follow(grammar, first, start_symbol)

        # Step 3 — LL(1)
        ll1_result = run_ll1_pipeline(grammar)

        # Step 4 — LR(1)
        states, transitions, lr_start, aug_grammar = build_lr1_states(grammar, first)
        action, goto_table, lr_conflicts = build_lr1_table(
            states, transitions, aug_grammar, lr_start
        )

        return jsonify({
            "corrected_input": input_string,
            "grammar":  serialize_grammar(grammar),
            "warnings": warnings,
            "formatted": format_grammar(grammar),
            "first":    {k: sorted(v) for k, v in first.items()},
            "follow":   {k: sorted(v) for k, v in follow.items()},
            "ll1": {
                "warnings":         ll1_result["warnings"],
                "grammar_modified": ll1_result["grammar_modified"],
                "final_grammar":    serialize_grammar(ll1_result["final_grammar"]),
                "table":            ll1_result["table"],
                "conflicts":        ll1_result["conflicts"],
                "formatted":        format_grammar(ll1_result["final_grammar"])
            },
            "lr1": {
                "action":       serialize_table(action),
                "goto":         serialize_table(goto_table),
                "conflicts":    lr_conflicts,
                "states_count": len(states)
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500    


# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True)