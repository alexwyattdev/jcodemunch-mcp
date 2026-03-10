"""Comprehensive tests for Swift language support."""

from jcodemunch_mcp.parser import parse_file, LANGUAGE_REGISTRY
from jcodemunch_mcp.parser.languages import LANGUAGE_EXTENSIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(source: str):
    return parse_file(source, "test.swift", "swift")


def symbols_by_kind(source: str, kind: str) -> list[str]:
    return [s.name for s in parse(source) if s.kind == kind]


def all_names(source: str) -> list[str]:
    return [s.name for s in parse(source)]


def sym_map(source: str) -> dict:
    """Return {qualified_name: Symbol} dict for easy assertions.

    Raises AssertionError if two symbols share the same qualified_name so
    tests cannot silently pass on a dict that dropped duplicate symbols.
    Use parse() directly for sources that legitimately contain duplicates
    (e.g. multiple extensions of the same type, overloaded init declarations).
    """
    result: dict = {}
    for s in parse(source):
        if s.qualified_name in result:
            raise AssertionError(
                f"sym_map: duplicate qualified_name {s.qualified_name!r} — "
                "use parse() directly for sources with intentional duplicates"
            )
        result[s.qualified_name] = s
    return result


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_swift_extension_registered():
    assert LANGUAGE_EXTENSIONS.get(".swift") == "swift"


def test_swift_in_registry():
    assert "swift" in LANGUAGE_REGISTRY


# ---------------------------------------------------------------------------
# Type declarations
# ---------------------------------------------------------------------------

TYPE_DECLARATIONS = """\
class Plain {}
struct AStruct {}
enum AEnum { case one }
protocol AProtocol {}
typealias MyInt = Int
"""


def test_class_indexed():
    assert "Plain" in symbols_by_kind(TYPE_DECLARATIONS, "class")


def test_struct_indexed():
    # tree-sitter-swift uses class_declaration for struct; kind is "class"
    assert "AStruct" in symbols_by_kind(TYPE_DECLARATIONS, "class")


def test_enum_indexed():
    assert "AEnum" in symbols_by_kind(TYPE_DECLARATIONS, "class")


def test_protocol_declaration_indexed():
    assert "AProtocol" in symbols_by_kind(TYPE_DECLARATIONS, "type")


def test_typealias_indexed():
    assert "MyInt" in symbols_by_kind(TYPE_DECLARATIONS, "type")


MODIFIERS = """\
public class PublicClass {}
final class FinalClass {}
private struct PrivateStruct {}
open class OpenBase {}
"""


def test_class_with_modifiers_indexed():
    names = symbols_by_kind(MODIFIERS, "class")
    assert "PublicClass" in names
    assert "FinalClass" in names
    assert "PrivateStruct" in names
    assert "OpenBase" in names


GENERIC_TYPES = """\
struct Stack<T> {
    func push(_ item: T) {}
}
class Box<T: Equatable> {
    func get() -> T { fatalError() }
}
"""


def test_generic_struct_indexed():
    assert "Stack" in symbols_by_kind(GENERIC_TYPES, "class")


def test_generic_class_indexed():
    assert "Box" in symbols_by_kind(GENERIC_TYPES, "class")


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

EXTENSION = """\
class Base {}
extension Base {
    func extended() {}
}
extension Base: CustomStringConvertible {
    var description: String { return "Base" }
}
"""


def test_extension_indexed():
    names = symbols_by_kind(EXTENSION, "class")
    # Both extensions of Base should appear; name comes from the extended type
    assert names.count("Base") >= 2


def test_extension_method_scoped_to_extended_type():
    # Extensions get a unique qualified_name ("Base+extension:<line>") so their
    # symbol IDs don't collide with the base class, but child methods still
    # use the base type name as qualifier → qualified_name = "Base.extended".
    syms = parse(EXTENSION)
    assert any(s.qualified_name == "Base.extended" for s in syms)


def test_extension_container_ids_are_unique():
    # Each extension must have a distinct symbol ID from the base class and
    # from one another so that _disambiguate_overloads never renames them.
    syms = parse(EXTENSION)
    containers = [s for s in syms if s.kind == "class" and s.name == "Base"]
    ids = [s.id for s in containers]
    assert len(ids) == len(set(ids)), "Extension container IDs must be unique"


def test_extension_methods_have_correct_parent():
    # Methods declared inside an extension must have their parent pointer set
    # to the extension container's ID (not the base class ID).
    syms = parse(EXTENSION)
    extended = next(s for s in syms if s.name == "extended")
    # The parent should be the extension container, not the plain base class.
    assert extended.parent is not None
    assert "+extension:" in extended.parent


# ---------------------------------------------------------------------------
# Actor
# ---------------------------------------------------------------------------

ACTOR = """\
actor DataStore {
    func fetch() -> String { "" }
    func save(_ data: String) {}
}
"""


def test_actor_indexed():
    assert "DataStore" in symbols_by_kind(ACTOR, "class")


def test_actor_methods_indexed():
    names = all_names(ACTOR)
    assert "fetch" in names
    assert "save" in names


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

FUNCTIONS = """\
func plain(x: Int) -> Int { x }
func withLabel(for value: String) -> Bool { false }
func asyncFetch(url: String) async throws -> Data { Data() }
func generic<T: Comparable>(_ a: T, _ b: T) -> T { a }
"""


def test_top_level_functions_indexed():
    names = symbols_by_kind(FUNCTIONS, "function")
    assert "plain" in names
    assert "withLabel" in names
    assert "asyncFetch" in names
    assert "generic" in names


def test_top_level_function_kind():
    m = sym_map(FUNCTIONS)
    assert m["plain"].kind == "function"


def test_function_signature_captured():
    m = sym_map(FUNCTIONS)
    sig = m["plain"].signature
    assert "func plain" in sig
    assert "x: Int" in sig
    assert "-> Int" in sig
    # Body braces should not be in the signature
    assert "{" not in sig


def test_generic_function_signature():
    m = sym_map(FUNCTIONS)
    sig = m["generic"].signature
    assert "<T" in sig


# ---------------------------------------------------------------------------
# Methods inside class/struct
# ---------------------------------------------------------------------------

METHODS = """\
class Service {
    func publicMethod() -> String { "" }
    private func privateMethod() {}
    static func staticMethod() -> Int { 0 }
    class func classMethod() {}
    override func overrideMethod() {}
}
"""


def test_class_methods_indexed():
    names = all_names(METHODS)
    assert "publicMethod" in names
    assert "privateMethod" in names
    assert "staticMethod" in names
    assert "classMethod" in names
    assert "overrideMethod" in names


def test_class_methods_are_kind_method():
    m = sym_map(METHODS)
    assert m["Service.publicMethod"].kind == "method"
    assert m["Service.staticMethod"].kind == "method"


def test_class_methods_scoped_to_parent():
    m = sym_map(METHODS)
    assert "Service.publicMethod" in m
    assert "Service.privateMethod" in m
    assert "Service.staticMethod" in m


# ---------------------------------------------------------------------------
# Protocol methods
# ---------------------------------------------------------------------------

PROTOCOL_METHODS = """\
protocol Repository {
    func findById(id: Int) -> String?
    func save(_ item: String) -> Bool
    func delete(id: Int)
}
"""


def test_protocol_indexed():
    assert "Repository" in symbols_by_kind(PROTOCOL_METHODS, "type")


def test_protocol_methods_indexed():
    names = all_names(PROTOCOL_METHODS)
    assert "findById" in names
    assert "save" in names
    assert "delete" in names


def test_protocol_methods_are_kind_method():
    m = sym_map(PROTOCOL_METHODS)
    assert m["Repository.findById"].kind == "method"


def test_protocol_method_scoped_to_protocol():
    m = sym_map(PROTOCOL_METHODS)
    assert "Repository.findById" in m
    assert "Repository.save" in m


# ---------------------------------------------------------------------------
# Init / Deinit
# ---------------------------------------------------------------------------

INIT_DEINIT = """\
class MyClass {
    init() {}
    init(value: Int) {}
    init?(coder: NSCoder) {}
    convenience init(name: String) {}
    deinit { cleanup() }
}
"""


def test_init_indexed():
    names = all_names(INIT_DEINIT)
    assert names.count("init") >= 1


def test_deinit_indexed():
    names = all_names(INIT_DEINIT)
    assert "deinit" in names


def test_init_kind_is_method():
    syms = parse(INIT_DEINIT)
    inits = [s for s in syms if s.name == "init"]
    assert all(s.kind == "method" for s in inits)


def test_deinit_kind_is_method():
    syms = parse(INIT_DEINIT)
    deinit = next(s for s in syms if s.name == "deinit")
    assert deinit.kind == "method"


# ---------------------------------------------------------------------------
# Subscript
# ---------------------------------------------------------------------------

SUBSCRIPT = """\
class Matrix {
    subscript(row: Int, col: Int) -> Double {
        get { data[row][col] }
        set { data[row][col] = newValue }
    }
}
"""


def test_subscript_indexed():
    names = all_names(SUBSCRIPT)
    assert "subscript" in names


def test_subscript_kind_is_method():
    m = sym_map(SUBSCRIPT)
    assert m["Matrix.subscript"].kind == "method"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONSTANTS = """\
let MAX_RETRY = 3
let BASE_URL = "https://example.com"
let GLOBAL_TAG = "global"
let lowercase = "not indexed"
var MUTABLE_UPPER = 42
"""


def test_upper_case_let_extracted():
    names = symbols_by_kind(CONSTANTS, "constant")
    assert "MAX_RETRY" in names
    assert "BASE_URL" in names
    assert "GLOBAL_TAG" in names


def test_lowercase_let_not_extracted():
    assert "lowercase" not in all_names(CONSTANTS)


def test_var_not_extracted():
    assert "MUTABLE_UPPER" not in all_names(CONSTANTS)


def test_constant_kind():
    m = sym_map(CONSTANTS)
    assert m["MAX_RETRY"].kind == "constant"


CLASS_CONSTANTS = """\
class Config {
    static let MAX_SIZE = 100
    static let BASE_PATH = "/api/v1"
    static var MUTABLE_FLAG = false
    let instanceName = "x"
}
struct Limits {
    static let MAX_COUNT = 50
}
"""


def test_static_let_extracted():
    names = symbols_by_kind(CLASS_CONSTANTS, "constant")
    assert "MAX_SIZE" in names
    assert "BASE_PATH" in names
    assert "MAX_COUNT" in names


def test_static_let_qualified_with_class():
    m = sym_map(CLASS_CONSTANTS)
    assert "Config.MAX_SIZE" in m
    assert "Config.BASE_PATH" in m
    assert "Limits.MAX_COUNT" in m


def test_static_var_not_extracted():
    assert "MUTABLE_FLAG" not in all_names(CLASS_CONSTANTS)


def test_instance_let_lowercase_not_extracted():
    assert "instanceName" not in all_names(CLASS_CONSTANTS)


# ---------------------------------------------------------------------------
# Attributes / Decorators
# ---------------------------------------------------------------------------

ATTRIBUTES = """\
@objc class MyVC: UIViewController {
    @objc func handleTap() {}
    @available(iOS 14, *) func newFeature() {}
    @discardableResult func compute() -> Int { 0 }
}
"""


def test_class_attribute_captured():
    m = sym_map(ATTRIBUTES)
    assert "@objc" in m["MyVC"].decorators


def test_method_attribute_captured():
    m = sym_map(ATTRIBUTES)
    assert "@objc" in m["MyVC.handleTap"].decorators


def test_available_attribute_captured():
    m = sym_map(ATTRIBUTES)
    attrs = m["MyVC.newFeature"].decorators
    assert any("available" in a for a in attrs)


def test_discardable_result_captured():
    m = sym_map(ATTRIBUTES)
    attrs = m["MyVC.compute"].decorators
    assert any("discardableResult" in a for a in attrs)


# ---------------------------------------------------------------------------
# Docstrings
# ---------------------------------------------------------------------------

DOCSTRINGS = """\
/// Fetches user data from the remote API.
/// - Parameter id: The user identifier
/// - Returns: User data string
func fetchUser(id: Int) -> String { "" }

/**
 * A service that manages user sessions.
 */
class SessionService {
    /// Starts a new session for the given user.
    func startSession(userId: Int) {}
}
"""


def test_triple_slash_doc_extracted():
    m = sym_map(DOCSTRINGS)
    assert "Fetches user data" in m["fetchUser"].docstring


def test_block_doc_extracted():
    m = sym_map(DOCSTRINGS)
    assert "manages user sessions" in m["SessionService"].docstring


def test_inline_triple_slash_doc():
    m = sym_map(DOCSTRINGS)
    assert "Starts a new session" in m["SessionService.startSession"].docstring


# ---------------------------------------------------------------------------
# Real-world patterns
# ---------------------------------------------------------------------------

UIVIEWCONTROLLER = """\
class ProfileViewController: UIViewController {
    static let STORYBOARD_ID = "ProfileVC"

    override func viewDidLoad() {
        super.viewDidLoad()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
    }

    @IBAction func saveButtonTapped(_ sender: UIButton) {}

    deinit { NotificationCenter.default.removeObserver(self) }
}
"""


def test_viewcontroller_class_indexed():
    assert "ProfileViewController" in symbols_by_kind(UIVIEWCONTROLLER, "class")


def test_viewcontroller_methods_indexed():
    names = all_names(UIVIEWCONTROLLER)
    assert "viewDidLoad" in names
    assert "viewWillAppear" in names
    assert "saveButtonTapped" in names
    assert "deinit" in names


def test_viewcontroller_constant_qualified():
    m = sym_map(UIVIEWCONTROLLER)
    assert "ProfileViewController.STORYBOARD_ID" in m


def test_ibaction_attribute_captured():
    m = sym_map(UIVIEWCONTROLLER)
    assert any("IBAction" in a for a in m["ProfileViewController.saveButtonTapped"].decorators)


SWIFTUI_VIEW = """\
import SwiftUI

struct CounterView: View {
    static let MAX_COUNT = 100

    var body: some View {
        Text("Hello")
    }

    func reset() {}
}

struct ContentView: View {
    var body: some View {
        CounterView()
    }
}
"""


def test_swiftui_struct_indexed():
    names = symbols_by_kind(SWIFTUI_VIEW, "class")
    assert "CounterView" in names
    assert "ContentView" in names


def test_swiftui_constant_qualified():
    m = sym_map(SWIFTUI_VIEW)
    assert "CounterView.MAX_COUNT" in m


def test_swiftui_method_indexed():
    assert "reset" in all_names(SWIFTUI_VIEW)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_file_returns_no_symbols():
    assert parse("") == []


def test_import_only_returns_no_symbols():
    src = """\
import Foundation
import UIKit
import Combine
"""
    assert parse(src) == []


def test_comment_only_returns_no_symbols():
    src = """\
// This is a comment
/// Doc comment
/* Block comment */
"""
    assert parse(src) == []
