"""Deterministic authorization boundary for every agent tool call."""
import hashlib
import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
import yaml
from shared.contracts import ToolCall, CallContext, ToolResult
from backend.app import db, mock_paytm, pii

LOCK = RLock()


def now():
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def load_registry():
    return yaml.safe_load((Path(__file__).resolve().parents[1] / 'tools.yaml').read_text())


def known_policy_ref(ref):
    if not isinstance(ref, str) or '#' not in ref:
        return False
    filename, section = ref.split('#', 1)
    if Path(filename).name != filename or not section:
        return False
    path = Path(__file__).resolve().parents[2] / 'engine' / 'policy_docs' / filename
    return path.is_file() and any(line.strip() == '## ' + section for line in path.read_text().splitlines())


def tool_definitions() -> list[dict]:
    definitions = []
    for tool in load_registry()['tools']:
        properties = {key: {'type': spec['type']} for key, spec in tool['args'].items()}
        if tool['tier'] in ('money_moving', 'sensitive'):
            properties['policy_ref'] = {'type': 'string', 'description': 'citation of the policy rule allowing this action'}
        definitions.append({'type': 'function', 'function': {'name': tool['name'], 'description': tool['description'], 'parameters': {'type': 'object', 'properties': properties, 'required': [key for key, spec in tool['args'].items() if spec.get('required')], 'additionalProperties': False}}})
    return definitions


def audit(call, ctx, tier, decision, result, key):
    return db.execute('INSERT INTO audit_log(ts,case_id,actor,tool,tier,args_masked_json,decision,reason,result_json,policy_ref,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (now(), ctx.case_id, ctx.approved_by or 'agent', call.name, tier, json.dumps(pii.mask_obj(call.args, ctx.session_id)), decision, pii.mask(result.reason, ctx.session_id) if result.reason else None, result.model_dump_json(), call.policy_ref or call.args.get('policy_ref'), key))


def execute(call: ToolCall, ctx: CallContext) -> ToolResult:
    # shortcut: serialize within one server process; use a transactional job ledger before multi-worker deployment.
    with LOCK:
        tool = next((item for item in load_registry()['tools'] if item['name'] == call.name), None)
        tier = tool['tier'] if tool else 'unknown'
        key = hashlib.sha256((ctx.case_id + call.name + json.dumps(call.args, sort_keys=True)).encode()).hexdigest()
        def finish(status, reason=None, data=None, approval_id=None, decision=None):
            result = ToolResult(status=status, reason=pii.mask(reason, ctx.session_id) if reason else None, data=data or {}, approval_id=approval_id)
            result.audit_id = audit(call, ctx, tier, decision or status, result, key)
            return result
        try:
            if tool is None:
                return finish('blocked', 'unknown tool')
            args = dict(call.args)
            policy_ref = call.policy_ref or args.pop('policy_ref', None)
            args.pop('policy_ref', None)
            if policy_ref is not None and not isinstance(policy_ref, str):
                return finish('error', 'policy_ref must be a string')
            if set(args) - set(tool['args']):
                return finish('error', 'unknown arguments')
            for name, spec in tool['args'].items():
                if name not in args:
                    if spec.get('required'):
                        return finish('error', 'missing argument: ' + name)
                    continue
                value = args[name]
                valid = (isinstance(value, str) and bool(value.strip())) if spec['type'] == 'string' else (type(value) is int if spec['type'] == 'integer' else type(value) in (int, float) and math.isfinite(value))
                if not valid:
                    return finish('error', 'invalid argument: ' + name)
            session = db.fetch_one('SELECT customer_id FROM sessions WHERE id=?', (ctx.session_id,))
            case = db.fetch_one('SELECT * FROM cases WHERE id=?', (ctx.case_id,))
            if not session or not case or session['customer_id'] != ctx.customer_id or case['customer_id'] != ctx.customer_id or case['session_id'] != ctx.session_id:
                return finish('blocked', 'context ownership mismatch')
            if not ctx.verified and tier != 'read_only':
                return finish('blocked', 'verification required')
            if tier == 'money_moving' and (not policy_ref or not policy_ref.strip()):
                return finish('blocked', 'policy_ref required')
            previous = db.fetch_one("SELECT id,result_json FROM audit_log WHERE idempotency_key=? AND decision='executed' ORDER BY id LIMIT 1", (key,))
            if previous and tier != 'read_only':
                result = ToolResult.model_validate_json(previous['result_json'])
                result.audit_id = previous['id']
                audit(call, ctx, tier, 'replayed', result, key)
                return result
            real_args = pii.unmask(args, ctx.session_id)
            if 'txn_id' in real_args:
                try:
                    mock_paytm.get_txn_status(ctx.customer_id, real_args['txn_id'])
                except ValueError as exc:
                    return finish('blocked', str(exc))
            if tier == 'sensitive' and mock_paytm.get_customer_profile(ctx.customer_id)['wallet_status'] == 'frozen':
                return finish('blocked', 'contact changes blocked during account compromise')
            needs_approval = tier == 'sensitive' and not ctx.step_up_passed
            if tier == 'money_moving':
                if not policy_ref or not policy_ref.strip():
                    return finish('blocked', 'policy_ref required')
                txn = mock_paytm.get_txn_status(ctx.customer_id, real_args['txn_id'])
                if txn['status'] not in tool['eligible_status']:
                    return finish('blocked', 'transaction status not eligible')
                if real_args['amount'] <= 0 or real_args['amount'] != txn['amount']:
                    return finish('blocked', 'amount must equal the positive debited amount')
                if not known_policy_ref(policy_ref):
                    return finish('blocked', 'unknown policy citation')
                needs_approval = real_args['amount'] > tool['cap_inr'] and not ctx.approved_by
            if needs_approval:
                masked_args = json.dumps(pii.mask_obj(args, ctx.session_id), sort_keys=True)
                pending = db.fetch_one("SELECT id FROM approvals WHERE case_id=? AND tool=? AND args_json=? AND status='pending'", (ctx.case_id, call.name, masked_args))
                approval_id = pending['id'] if pending else db.execute("INSERT INTO approvals(case_id,tool,args_json,policy_ref,status,created_at) VALUES(?,?,?,?,'pending',?)", (ctx.case_id, call.name, masked_args, policy_ref, now()))
                db.execute("UPDATE cases SET status='awaiting_approval' WHERE id=?", (ctx.case_id,))
                return finish('needs_approval', 'human approval required', approval_id=approval_id)
            owner = {'case_id': ctx.case_id} if call.name == 'escalate_to_human' else {'customer_id': ctx.customer_id}
            data = mock_paytm.DISPATCH[call.name](**owner, **real_args)
            return finish('ok', data=pii.mask_obj(data, ctx.session_id), decision='executed')
        except ValueError as exc:
            return finish('blocked' if tier == 'money_moving' else 'error', str(exc))
        except Exception as exc:
            return finish('error', str(exc))
