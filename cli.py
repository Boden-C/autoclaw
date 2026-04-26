import argparse
import sys
import time
from collections import deque
from dataclasses import dataclass

from pywinauto import Desktop
from pywinauto.keyboard import send_keys
from pywinauto.uia_defines import IUIA
from pywinauto.uia_element_info import UIAElementInfo


@dataclass
class TreeNode:
    node_id: int
    wrapper: object
    depth: int
    name: str
    control_type: str
    actions: list | None
    actionable: bool
    focused: bool
    contains_focus: bool
    children: list


PASSIVE_ACTIONS = {"focus", "read", "texts"}
ALWAYS_AVAILABLE_ACTIONS = ["focus", "click-input", "read"]
LIKELY_ACTIONABLE_CONTROL_TYPES = {
    "Button",
    "CheckBox",
    "ComboBox",
    "Edit",
    "Hyperlink",
    "ListItem",
    "MenuItem",
    "RadioButton",
    "ScrollBar",
    "Slider",
    "SplitButton",
    "TabItem",
    "TreeItem",
    "Window",
}


def safe_text(value):
    try:
        if value is None:
            return ""
        return str(value).replace("\r", "\\r").replace("\n", "\\n")
    except Exception:
        return "<unreadable>"


def emit(line=""):
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.buffer.write((line + "\n").encode(encoding, errors="backslashreplace"))


def truncate_text(value, max_length):
    if len(value) <= max_length:
        return value
    if max_length <= 3:
        return "." * max_length
    return value[: max_length - 3] + "..."


def quote_name(value, max_length):
    return "'" + truncate_text(value, max_length) + "'"


def get_control_type(info):
    try:
        control_type = safe_text(getattr(info, "control_type", "")).strip()
    except Exception:
        control_type = ""
    return control_type or "Element"


def get_name(info):
    try:
        return safe_text(info.name).strip()
    except Exception:
        return ""


def get_display_label(name, control_type, max_name_length):
    if name:
        return f"{quote_name(name, max_name_length)} {control_type}"
    return f"Unnamed {control_type}"


def get_window_title(wrapper):
    try:
        return safe_text(wrapper.window_text()).strip()
    except Exception:
        return ""


def normalize_depth(value):
    if value is None or value < 0:
        return None
    return value


def get_focused_runtime_id():
    try:
        focused_element = IUIA().get_focused_element()
        return UIAElementInfo(focused_element).runtime_id
    except Exception:
        return None


def get_focused_summary(max_name_length):
    try:
        focused_info = UIAElementInfo(IUIA().get_focused_element())
        return get_display_label(get_name(focused_info), get_control_type(focused_info), max_name_length)
    except Exception:
        return "<unavailable>"


def select_window(desktop, title_contains=None):
    windows = desktop.windows(active_only=True) if not title_contains else desktop.windows()
    if not windows:
        raise RuntimeError("No top-level windows found.")

    if not title_contains:
        return windows[0]

    needle = title_contains.casefold()
    for window in windows:
        if needle in get_window_title(window).casefold():
            return window

    raise RuntimeError(f"No window title contains {title_contains!r}.")


def supports_property(wrapper, attr_name):
    try:
        getattr(wrapper, attr_name)
        return True
    except Exception:
        return False


def get_supported_actions(wrapper):
    actions = []
    control_type = ""
    try:
        control_type = get_control_type(wrapper.element_info)
    except Exception:
        control_type = ""

    if supports_property(wrapper, "iface_invoke"):
        actions.append("invoke")
    if supports_property(wrapper, "iface_selection_item"):
        actions.append("select")
    if supports_property(wrapper, "iface_toggle"):
        actions.extend(["toggle", "get-toggle-state"])
    if supports_property(wrapper, "iface_expand_collapse"):
        actions.extend(["expand", "collapse"])
    if supports_property(wrapper, "iface_value"):
        actions.extend(["set-text", "append-text", "get-value", "send"])
    if supports_property(wrapper, "iface_text"):
        actions.extend(["type-keys", "send"])
    if supports_property(wrapper, "iface_range_value"):
        actions.extend(["set-value", "get-range-value"])
    if supports_property(wrapper, "iface_scroll"):
        actions.append("scroll")
    if supports_property(wrapper, "iface_window"):
        actions.extend(["close", "minimize", "maximize", "restore"])

    actions.extend(ALWAYS_AVAILABLE_ACTIONS)

    if hasattr(wrapper, "click"):
        actions.append("click")
    if hasattr(wrapper, "set_edit_text"):
        actions.extend(["set-text", "append-text", "send"])
    if hasattr(wrapper, "texts"):
        actions.append("texts")
    if control_type in ("ComboBox", "Edit"):
        actions.append("send")

    deduped = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped


def is_actionable_actions(actions):
    return any(action not in PASSIVE_ACTIONS for action in actions)


def is_likely_actionable(control_type):
    return control_type in LIKELY_ACTIONABLE_CONTROL_TYPES


def get_node_actions(node):
    if node.actions is None:
        node.actions = get_supported_actions(node.wrapper)
    return node.actions


def is_actionable_node(node):
    return node.actionable


def is_low_value_container(node):
    if node.name:
        return False
    return node.control_type in ("AppBar", "Group", "Image", "Pane", "Tab", "TitleBar")


def is_text_leaf(node):
    return not node.children and node.control_type == "Text" and bool(node.name)


def is_opaque_leaf(node):
    return not node.children


def format_id_span(start_id, end_id):
    if start_id == end_id:
        return f"[{start_id}]"
    return f"[{start_id}-{end_id}]"


def render_line(node, max_name_length, show_actions):
    label = get_display_label(node.name, node.control_type, max_name_length)
    focus_marker = ""
    if node.focused:
        focus_marker = " <FOCUSED>"
    elif node.contains_focus:
        focus_marker = " <FOCUS-PATH>"

    if not show_actions:
        return f"[{node.node_id}] {label}{focus_marker}"

    interesting = [action for action in get_node_actions(node) if action not in PASSIVE_ACTIONS]
    if not interesting:
        return f"[{node.node_id}] {label}{focus_marker}"
    return f"[{node.node_id}] {label}{focus_marker} {{{', '.join(interesting)}}}"


def render_merged_text_run(nodes, indent, max_name_length):
    texts = [quote_name(node.name, max_name_length) for node in nodes[:4]]
    label = ", ".join(texts)
    if len(nodes) > 4:
        label += ", ..."
    return f"{indent}{format_id_span(nodes[0].node_id, nodes[-1].node_id)} {label} Text"


def render_merged_leaf_run(nodes, indent, max_name_length):
    label = get_display_label(nodes[0].name, nodes[0].control_type, max_name_length)
    return f"{indent}{format_id_span(nodes[0].node_id, nodes[-1].node_id)} {len(nodes)}x {label}"


def compressible_leaf_run(nodes, index):
    node = nodes[index]
    if not is_opaque_leaf(node):
        return 0

    if is_text_leaf(node):
        run_length = 1
        for next_index in range(index + 1, len(nodes)):
            candidate = nodes[next_index]
            if is_text_leaf(candidate):
                run_length += 1
                continue
            break
        return run_length

    if not is_low_value_container(node):
        return 0

    run_length = 1
    for next_index in range(index + 1, len(nodes)):
        candidate = nodes[next_index]
        if not is_opaque_leaf(candidate):
            break
        if candidate.name != node.name or candidate.control_type != node.control_type or not is_low_value_container(candidate):
            break
        run_length += 1
    return run_length


def should_suppress_children(node):
    if node.control_type == "Edit":
        return all(child.control_type in ("Image", "Text") for child in node.children)

    if node.control_type == "ListItem":
        return all(child.control_type == "Edit" for child in node.children)

    return False


def should_omit_node(node):
    if node.children:
        return False
    return not node.name and not is_actionable_node(node)


def should_flatten_node(node):
    if node.name:
        return False
    if is_actionable_node(node):
        return False
    return len(node.children) == 1


def node_has_meaning(node):
    if node.focused or node.contains_focus:
        return True
    if node.name or node.actionable:
        return True
    return any(node_has_meaning(child) for child in node.children)


def normalize_nodes(nodes, forced_depth=None):
    normalized = []

    for node in nodes:
        children = normalize_nodes(node.children)

        if forced_depth is not None:
            node.depth = forced_depth
        node.children = children

        if should_omit_node(node):
            continue

        if not node.name and not node.actionable:
            if children:
                normalized.extend(normalize_nodes(children, forced_depth=node.depth))
            continue

        normalized.append(node)

    return normalized


def render_children(nodes, max_name_length, show_actions):
    lines = []
    nodes = normalize_nodes(nodes)
    index = 0

    while index < len(nodes):
        node = nodes[index]
        indent = "  " * node.depth
        run_length = compressible_leaf_run(nodes, index)

        if is_text_leaf(node) and run_length >= 2:
            lines.append(render_merged_text_run(nodes[index:index + run_length], indent, max_name_length))
            index += run_length
            continue

        if run_length >= 3:
            lines.append(render_merged_leaf_run(nodes[index:index + run_length], indent, max_name_length))
            index += run_length
            continue

        lines.append(f"{indent}{render_line(node, max_name_length, show_actions)}")
        if node.children and not should_suppress_children(node):
            lines.extend(render_children(node.children, max_name_length, show_actions))
        index += 1

    return lines


def build_tree(wrapper, max_depth, include_actions=False):
    counter = 0
    focused_runtime_id = get_focused_runtime_id()
    max_depth = normalize_depth(max_depth)

    def visit(current_wrapper, depth):
        nonlocal counter
        info = current_wrapper.element_info
        control_type = get_control_type(info)
        runtime_id = None
        try:
            runtime_id = info.runtime_id
        except Exception:
            runtime_id = None
        actions = get_supported_actions(current_wrapper) if include_actions else None

        node = TreeNode(
            node_id=counter,
            wrapper=current_wrapper,
            depth=depth,
            name=get_name(info),
            control_type=control_type,
            actions=actions,
            actionable=is_actionable_actions(actions) if actions is not None else is_likely_actionable(control_type),
            focused=bool(focused_runtime_id and runtime_id == focused_runtime_id),
            contains_focus=False,
            children=[],
        )
        counter += 1

        if max_depth is not None and depth >= max_depth:
            node.contains_focus = node.focused
            return node

        try:
            children = current_wrapper.children()
        except Exception:
            node.contains_focus = node.focused
            return node

        for child in children:
            node.children.append(visit(child, depth + 1))
        node.contains_focus = node.focused or any(child.contains_focus for child in node.children)
        return node

    return visit(wrapper, 0)


def flatten_tree(root):
    nodes = []

    def visit(node):
        nodes.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return nodes


def dump_tree(wrapper, max_depth, max_name_length, show_actions):
    root = build_tree(wrapper, max_depth=max_depth, include_actions=show_actions)
    focused_nodes = [node for node in flatten_tree(root) if node.focused]
    if focused_nodes:
        emit(f"Focused: {render_line(focused_nodes[0], max_name_length, show_actions=False)}")
    else:
        emit(f"Focused: {get_focused_summary(max_name_length)} <outside selected window>")
    for line in render_children([root], max_name_length=max_name_length, show_actions=show_actions):
        emit(line)
    return root


def matches(node, args):
    if args.node_id is not None:
        return node.node_id == args.node_id

    if args.name_contains:
        if args.name_contains.casefold() not in node.name.casefold():
            return False

    if args.control_type:
        if args.control_type.casefold() != node.control_type.casefold():
            return False

    if args.unnamed_only and node.name:
        return False

    if args.actionable_only:
        actions = get_node_actions(node)
        if all(action in PASSIVE_ACTIONS for action in actions):
            return False

    return True


def find_nodes(root, args):
    matches_found = []
    for node in flatten_tree(root):
        if matches(node, args):
            matches_found.append(node)
    return matches_found


def resolve_target(root, args):
    matches_found = find_nodes(root, args)
    if not matches_found:
        raise RuntimeError("No matching node found.")

    if args.match_index < 0 or args.match_index >= len(matches_found):
        raise RuntimeError(f"match-index {args.match_index} is out of range for {len(matches_found)} matches.")

    return matches_found[args.match_index]


def try_invoke(wrapper, method_name, *args):
    method = getattr(wrapper, method_name, None)
    if method is None:
        raise AttributeError(f"{method_name} is not available.")
    return method(*args)


def perform_set_text(wrapper, text, append):
    if hasattr(wrapper, "set_edit_text"):
        if append:
            existing = read_value(wrapper)
            wrapper.set_edit_text(existing + text)
        else:
            wrapper.set_edit_text(text)
        return "set_edit_text"

    if supports_property(wrapper, "iface_value"):
        try:
            if append:
                existing = read_value(wrapper)
                wrapper.iface_value.SetValue(existing + text)
            else:
                wrapper.iface_value.SetValue(text)
            return "iface_value.SetValue"
        except Exception:
            pass

    if hasattr(wrapper, "set_focus"):
        wrapper.set_focus()
    try:
        if not append:
            wrapper.type_keys("^a{BACKSPACE}", set_foreground=True)
        wrapper.type_keys(text, with_spaces=True, with_tabs=True, with_newlines=True, set_foreground=True)
        return "type_keys"
    except Exception:
        try:
            wrapper.click_input()
        except Exception:
            pass
        if not append:
            send_keys("^a{BACKSPACE}")
        send_keys(text, with_spaces=True, with_tabs=True, with_newlines=True)
        return "send_keys"


def read_value(wrapper):
    if hasattr(wrapper, "get_value"):
        try:
            return safe_text(wrapper.get_value())
        except Exception:
            pass

    if supports_property(wrapper, "iface_value"):
        try:
            return safe_text(wrapper.iface_value.CurrentValue)
        except Exception:
            pass

    try:
        return safe_text(wrapper.window_text())
    except Exception:
        return ""


def perform_action(node, args):
    wrapper = node.wrapper
    action = args.action

    if action == "auto":
        if supports_property(wrapper, "iface_invoke"):
            wrapper.invoke()
            return "invoke"
        if supports_property(wrapper, "iface_selection_item"):
            wrapper.select()
            return "select"
        if supports_property(wrapper, "iface_toggle"):
            wrapper.toggle()
            return "toggle"
        wrapper.click_input()
        return "click_input"

    if action == "click":
        if hasattr(wrapper, "click"):
            wrapper.click()
            return "click"
        if supports_property(wrapper, "iface_invoke"):
            wrapper.invoke()
            return "invoke"
        if supports_property(wrapper, "iface_selection_item"):
            wrapper.select()
            return "select"
        wrapper.click_input()
        return "click_input"
    if action == "click-input":
        wrapper.click_input()
        return "click_input"
    if action == "invoke":
        wrapper.invoke()
        return "invoke"
    if action == "select":
        wrapper.select()
        return "select"
    if action == "toggle":
        wrapper.toggle()
        return "toggle"
    if action == "expand":
        wrapper.expand()
        return "expand"
    if action == "collapse":
        wrapper.collapse()
        return "collapse"
    if action == "focus":
        wrapper.set_focus()
        return "focus"
    if action == "set-text":
        if args.text is None:
            raise RuntimeError("--text is required for set-text.")
        return perform_set_text(wrapper, args.text, append=False)
    if action == "append-text":
        if args.text is None:
            raise RuntimeError("--text is required for append-text.")
        return perform_set_text(wrapper, args.text, append=True)
    if action == "type-keys":
        if args.text is None:
            raise RuntimeError("--text is required for type-keys.")
        wrapper.type_keys(args.text, with_spaces=True, with_tabs=True, with_newlines=True, set_foreground=True)
        return "type_keys"
    if action == "send":
        if hasattr(wrapper, "set_focus"):
            wrapper.set_focus()
        try:
            wrapper.type_keys("{ENTER}", set_foreground=True)
            return "send"
        except Exception:
            try:
                wrapper.click_input()
            except Exception:
                pass
            send_keys("{ENTER}")
            return "send_keys"
    if action == "set-value":
        if args.value is None:
            raise RuntimeError("--value is required for set-value.")
        if hasattr(wrapper, "set_value"):
            wrapper.set_value(args.value)
            return "set_value"
        wrapper.iface_range_value.SetValue(args.value)
        return "iface_range_value.SetValue"
    if action == "scroll":
        if not args.direction or not args.amount:
            raise RuntimeError("--direction and --amount are required for scroll.")
        wrapper.scroll(args.direction, args.amount, count=args.count)
        return "scroll"
    if action == "close":
        wrapper.close()
        return "close"
    if action == "minimize":
        wrapper.minimize()
        return "minimize"
    if action == "maximize":
        wrapper.maximize()
        return "maximize"
    if action == "restore":
        wrapper.restore()
        return "restore"

    raise RuntimeError(f"Unsupported action: {action}")


def read_texts(wrapper):
    try:
        values = wrapper.texts()
        cleaned = [safe_text(value).strip() for value in values if safe_text(value).strip()]
        return cleaned
    except Exception:
        return []


def dump_subtree(node, max_depth, max_name_length, show_actions):
    root = build_tree(node.wrapper, max_depth=max_depth, include_actions=show_actions)
    for line in render_children([root], max_name_length=max_name_length, show_actions=show_actions):
        emit(line)


def add_window_argument(parser):
    parser.add_argument(
        "--window-title-contains",
        default="",
        help="Match a top-level window title by substring. Default: active window.",
    )


def add_tree_arguments(parser):
    parser.add_argument(
        "--max-depth",
        type=int,
        default=-1,
        help="Maximum child depth to traverse. Use -1 for full depth. Default: -1.",
    )
    parser.add_argument(
        "--max-name-length",
        type=int,
        default=48,
        help="Maximum visible characters for a control name before truncating with .... Default: 48.",
    )
    parser.add_argument(
        "--show-actions",
        action="store_true",
        help="Show supported interaction actions inline in the tree.",
    )


def add_match_arguments(parser):
    parser.add_argument("--node-id", type=int, default=None, help="Exact node id from the tree output.")
    parser.add_argument("--name-contains", default="", help="Case-insensitive substring match on node name.")
    parser.add_argument("--control-type", default="", help="Exact UIA control type filter, for example Button or Edit.")
    parser.add_argument("--match-index", type=int, default=0, help="Zero-based match index when multiple nodes match.")
    parser.add_argument("--unnamed-only", action="store_true", help="Only match unnamed nodes.")
    parser.add_argument("--actionable-only", action="store_true", help="Only match nodes with interaction actions.")


def parse_args():
    parser = argparse.ArgumentParser(description="Compact pywinauto UIA inspector and interaction CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    windows_parser = subparsers.add_parser("windows", help="List top-level windows.")
    windows_parser.add_argument("--limit", type=int, default=50, help="Maximum windows to print. Default: 50.")

    tree_parser = subparsers.add_parser("tree", help="Dump a compressed UI tree.")
    add_window_argument(tree_parser)
    add_tree_arguments(tree_parser)

    find_parser = subparsers.add_parser("find", help="Find nodes by selector and print ids.")
    add_window_argument(find_parser)
    add_tree_arguments(find_parser)
    add_match_arguments(find_parser)

    act_parser = subparsers.add_parser("act", help="Perform an interaction on a matched node.")
    add_window_argument(act_parser)
    act_parser.add_argument(
        "--action",
        required=True,
        choices=[
            "auto",
            "append-text",
            "click",
            "click-input",
            "close",
            "collapse",
            "expand",
            "focus",
            "invoke",
            "maximize",
            "minimize",
            "restore",
            "scroll",
            "select",
            "send",
            "set-text",
            "set-value",
            "toggle",
            "type-keys",
        ],
        help="Interaction to perform.",
    )
    add_match_arguments(act_parser)
    act_parser.add_argument("--text", default=None, help="Text payload for set-text, append-text, or type-keys.")
    act_parser.add_argument("--value", type=float, default=None, help="Numeric value for set-value.")
    act_parser.add_argument("--direction", default="", help="Scroll direction: up, down, left, or right.")
    act_parser.add_argument("--amount", default="", help="Scroll amount: line or page.")
    act_parser.add_argument("--count", type=int, default=1, help="Repeat count for scroll. Default: 1.")
    act_parser.add_argument("--max-depth", type=int, default=-1, help="Maximum depth to search for nodes. Use -1 for full depth.")
    act_parser.add_argument("--max-name-length", type=int, default=48, help="Name truncation length for output.")
    act_parser.add_argument(
        "--after-tree-depth",
        type=int,
        default=3,
        help="Depth for the refreshed tree printed after the action. Use -1 for full depth. Default: 3.",
    )
    act_parser.add_argument(
        "--no-after-tree",
        action="store_true",
        help="Skip the refreshed tree after the action.",
    )
    act_parser.add_argument(
        "--show-actions",
        action="store_true",
        help="Show supported actions in the refreshed tree.",
    )

    read_parser = subparsers.add_parser("read", help="Read values or a subtree from a matched node.")
    add_window_argument(read_parser)
    add_match_arguments(read_parser)
    read_parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "children", "subtree", "summary", "texts", "value"],
        help="Read mode. Default: auto.",
    )
    read_parser.add_argument("--max-depth", type=int, default=-1, help="Maximum depth for subtree mode. Use -1 for full depth.")
    read_parser.add_argument("--max-name-length", type=int, default=48, help="Name truncation length for subtree mode.")
    read_parser.add_argument("--show-actions", action="store_true", help="Show actions in subtree mode.")

    return parser.parse_args()


def run_windows(args):
    desktop = Desktop(backend="uia")
    for index, window in enumerate(desktop.windows()[:args.limit]):
        emit(f"[{index}] {quote_name(get_window_title(window), 96)} {get_control_type(window.element_info)}")
    return 0


def run_tree(args):
    desktop = Desktop(backend="uia")
    window = select_window(desktop, title_contains=args.window_title_contains)
    dump_tree(window, max_depth=args.max_depth, max_name_length=args.max_name_length, show_actions=args.show_actions)
    return 0


def run_find(args):
    desktop = Desktop(backend="uia")
    window = select_window(desktop, title_contains=args.window_title_contains)
    root = build_tree(window, max_depth=args.max_depth, include_actions=False)
    matches_found = find_nodes(root, args)

    if not matches_found:
        raise RuntimeError("No matching node found.")

    for node in matches_found:
        emit(render_line(node, args.max_name_length, args.show_actions))
    return 0


def run_act(args):
    desktop = Desktop(backend="uia")
    window = select_window(desktop, title_contains=args.window_title_contains)
    root = build_tree(window, max_depth=args.max_depth, include_actions=False)
    node = resolve_target(root, args)
    method = perform_action(node, args)
    emit(f"{method}: {render_line(node, args.max_name_length, show_actions=False)}")
    if args.no_after_tree:
        return 0
    time.sleep(0.8)
    refreshed_window = select_window(desktop, title_contains=args.window_title_contains)
    dump_tree(
        refreshed_window,
        max_depth=args.after_tree_depth,
        max_name_length=args.max_name_length,
        show_actions=args.show_actions,
    )
    return 0


def run_read(args):
    desktop = Desktop(backend="uia")
    window = select_window(desktop, title_contains=args.window_title_contains)
    root = build_tree(window, max_depth=max(args.max_depth, 12), include_actions=False)
    node = resolve_target(root, args)

    if args.mode == "summary":
        emit(render_line(node, args.max_name_length, show_actions=False))
        return 0

    if args.mode == "value":
        emit(read_value(node.wrapper))
        return 0

    if args.mode == "texts":
        texts = read_texts(node.wrapper)
        for value in texts:
            emit(value)
        return 0

    if args.mode == "children":
        child_root = build_tree(node.wrapper, max_depth=1, include_actions=args.show_actions)
        for line in render_children(child_root.children, max_name_length=args.max_name_length, show_actions=args.show_actions):
            emit(line)
        return 0

    if args.mode == "subtree":
        dump_subtree(node, max_depth=args.max_depth, max_name_length=args.max_name_length, show_actions=args.show_actions)
        return 0

    value = read_value(node.wrapper)
    if value:
        emit(value)
        return 0

    texts = read_texts(node.wrapper)
    if texts:
        for text in texts:
            emit(text)
        return 0

    dump_subtree(node, max_depth=args.max_depth, max_name_length=args.max_name_length, show_actions=args.show_actions)
    return 0


def main():
    args = parse_args()

    if args.command == "windows":
        return run_windows(args)
    if args.command == "tree":
        return run_tree(args)
    if args.command == "find":
        return run_find(args)
    if args.command == "act":
        return run_act(args)
    if args.command == "read":
        return run_read(args)

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
