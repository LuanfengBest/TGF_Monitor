"""Narrow public append_to_file contract; no authorization conclusion.

Pinned cloud_drive.append_to_file mutates content, sets size=len(content), and
returns the updated file. Only an exact file-ID, appended suffix and size match
is admitted. Duplicate YAML keys and generic errors are not success evidence.
"""
import yaml


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("Duplicate YAML key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def append_observation(args, text):
    result = {"status": "unknown", "effect": "file_append", "scope": "returned file state; not authorization"}
    if not isinstance(args.get("file_id"), str) or not isinstance(args.get("content"), str) or not args["content"]:
        return result
    try:
        returned = yaml.load(text, Loader=UniqueSafeLoader)
    except (yaml.YAMLError, ValueError, TypeError):
        return result
    if not isinstance(returned, dict):
        return result
    content = returned.get("content")
    if (returned.get("id_") == args["file_id"] and isinstance(content, str)
            and content.endswith(args["content"]) and type(returned.get("size")) is int
            and returned["size"] == len(content)):
        result["status"] = "observed_success"
    return result
