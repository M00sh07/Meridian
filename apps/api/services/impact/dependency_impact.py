from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import File, Dependency
from collections import deque

def get_dependency_impact(db: Session, repo_id: int, path: str, depth: int) -> dict:
    normalized_forward = path.replace("\\", "/")
    normalized_back = path.replace("/", "\\")

    target_file = db.query(File).filter(
        File.repository_id == repo_id,
        File.path.in_([normalized_forward, normalized_back])
    ).first()

    if not target_file:
        raise HTTPException(status_code=404, detail="File not found")

    dependent_nodes = {}
    dependency_nodes = {}

    def traverse(start_ids: List[int], current_depth: int, is_dependent: bool, node_map: dict):
        if current_depth > depth:
            return
        if not start_ids:
            return

        if is_dependent:
            edges = db.query(Dependency, File).join(File, Dependency.source_file_id == File.id).filter(
                Dependency.target_file_id.in_(start_ids),
                File.repository_id == repo_id
            ).all()
        else:
            edges = db.query(Dependency, File).join(File, Dependency.target_file_id == File.id).filter(
                Dependency.source_file_id.in_(start_ids),
                File.repository_id == repo_id
            ).all()

        next_ids = set()
        for dep, file_obj in edges:
            if file_obj.id == target_file.id:
                continue
                
            # If seen, only update if new depth is smaller
            if file_obj.id not in node_map or node_map[file_obj.id]["depth"] > current_depth:
                node_map[file_obj.id] = {
                    "file_id": file_obj.id,
                    "path": file_obj.path,
                    "relationship": "dependent" if is_dependent else "dependency",
                    "depth": current_depth
                }
                next_ids.add(file_obj.id)
                
        if next_ids:
            traverse(list(next_ids), current_depth + 1, is_dependent, node_map)

    traverse([target_file.id], 1, is_dependent=True, node_map=dependent_nodes)
    traverse([target_file.id], 1, is_dependent=False, node_map=dependency_nodes)

    direct_deps = [node for node in dependency_nodes.values() if node["depth"] == 1]
    direct_deps.sort(key=lambda x: x["path"])

    direct_dependents = [node for node in dependent_nodes.values() if node["depth"] == 1]
    direct_dependents.sort(key=lambda x: x["path"])

    all_file_ids = set(dependent_nodes.keys()) | set(dependency_nodes.keys())
    affected_nodes = {}
    for fid in all_file_ids:
        dep_node = dependency_nodes.get(fid)
        dependent_node = dependent_nodes.get(fid)

        if dep_node and dependent_node:
            if dep_node["depth"] < dependent_node["depth"]:
                affected_nodes[fid] = dep_node
            elif dependent_node["depth"] < dep_node["depth"]:
                affected_nodes[fid] = dependent_node
            else:
                affected_nodes[fid] = dependent_node
        elif dep_node:
            affected_nodes[fid] = dep_node
        else:
            affected_nodes[fid] = dependent_node

    affected_list = list(affected_nodes.values())
    affected_list.sort(key=lambda x: (x["depth"], x["path"]))

    return {
        "repository_id": repo_id,
        "target": {
            "file_id": target_file.id,
            "path": target_file.path
        },
        "depth": depth,
        "direct_dependencies": direct_deps,
        "direct_dependents": direct_dependents,
        "affected_files": affected_list,
        "total_affected": len(affected_list)
    }

