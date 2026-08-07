from src.graph.workflow import build_graph


def test_build_graph_returns_compiled_graph():
    graph = build_graph(object())
    assert graph is not None
    assert hasattr(graph, "get_state")
