"""
TR118: Small ONNX graph sanitizers for TensorRT compatibility.

These transforms are intentionally minimal and local-first: they only apply
safe, semantics-preserving rewrites that unblock known TensorRT build issues.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _replace_constant_of_shape_empty_shape(model: Any) -> int:
    """
    TensorRT INT8 builder (TRT 10.x on Windows) can fail on ConstantOfShape with an
    empty shape tensor (scalar output), producing an internal ONNXTRT_ShapeSlice
    node that fails to build.

    This rewrite replaces:
      ConstantOfShape(shape=Constant([]), value=v) -> Constant(scalar(v))

    Only the empty-shape case is handled to avoid bloating the ONNX file by
    materializing large constant tensors.
    """
    import onnx  # local import: avoid forcing onnx for users not touching TRT
    from onnx import helper, numpy_helper

    out_to_node: dict[str, Any] = {}
    for n in model.graph.node:
        for o in n.output:
            out_to_node[str(o)] = n

    new_nodes = []
    replaced = 0
    for n in model.graph.node:
        if n.op_type != "ConstantOfShape" or not n.input:
            new_nodes.append(n)
            continue

        shape_src = out_to_node.get(str(n.input[0]))
        shape_val = None
        if shape_src is not None and shape_src.op_type == "Constant":
            for a in shape_src.attribute:
                if a.name == "value":
                    shape_val = numpy_helper.to_array(a.t)
                    break
        if shape_val is None or shape_val.size != 0:
            new_nodes.append(n)
            continue

        # Extract fill value + dtype (defaults to float32 0.0 per exporter pattern).
        fill_dtype = onnx.TensorProto.FLOAT
        fill_val = 0.0
        for a in n.attribute:
            if a.name != "value":
                continue
            fill_dtype = int(a.t.data_type) or onnx.TensorProto.FLOAT
            arr = numpy_helper.to_array(a.t)
            if arr.size:
                fill_val = float(arr.reshape(-1)[0])
            break

        tensor = helper.make_tensor(
            name=(n.name or "ConstantOfShape") + "_scalar",
            data_type=fill_dtype,
            dims=[],
            vals=[fill_val],
        )
        new_nodes.append(
            helper.make_node(
                "Constant",
                inputs=[],
                outputs=list(n.output),
                name=n.name,
                value=tensor,
            )
        )
        replaced += 1

    if replaced:
        model.graph.ClearField("node")
        model.graph.node.extend(new_nodes)
    return replaced


def sanitize_onnx_file(path: Path) -> dict[str, Any]:
    import onnx  # local import

    if not path.exists():
        return {"changed": False, "reason": "missing"}

    model = onnx.load(str(path))
    replaced = _replace_constant_of_shape_empty_shape(model)
    if replaced:
        onnx.checker.check_model(model)
        onnx.save(model, str(path))
        return {"changed": True, "constant_of_shape_scalar_rewrites": replaced}
    return {"changed": False, "constant_of_shape_scalar_rewrites": 0}

