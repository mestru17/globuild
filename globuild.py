#!/usr/bin/env python3

from __future__ import annotations
import os
from pathlib import Path
from typing import Callable, Iterable, List


class Artifact:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __eq__(self, __o: object) -> bool:
        return hasattr(__o, "path") and self.path == __o.path

    def __hash__(self) -> int:
        return hash(self.path)

    def __str__(self) -> str:
        return format(self.path)

    def dependencies(self) -> Iterable[Artifact]:
        raise NotImplementedError()

    def accept(self, visitor: ArtifactVisitor):
        raise NotImplementedError()


class SourceArtifact(Artifact):
    def __init__(self, path: Path) -> None:
        super().__init__(path)

    def dependencies(self) -> Iterable[Artifact]:
        return []

    def accept(self, visitor: ArtifactVisitor):
        visitor.visit_source(self)


class ObjectArtifact(Artifact):
    def __init__(self, path: Path, source: SourceArtifact) -> None:
        super().__init__(path)
        self.source = source

    def dependencies(self) -> Iterable[Artifact]:
        return [self.source]

    def accept(self, visitor: ArtifactVisitor):
        self.source.accept(visitor)
        visitor.visit_object(self)


class LibraryArtifact(Artifact):
    def __init__(self, path: Path, *objects: ObjectArtifact) -> None:
        super().__init__(path)
        self.objects = objects

    def dependencies(self) -> Iterable[Artifact]:
        return self.objects

    def accept(self, visitor: ArtifactVisitor):
        for obj in self.objects:
            obj.accept(visitor)
        self._visit_library(visitor)

    def _visit_library(self, visitor: ArtifactVisitor):
        raise NotImplementedError()


class StaticLibraryArtifact(LibraryArtifact):
    def __init__(self, path: Path, *objects: ObjectArtifact) -> None:
        super().__init__(path, *objects)

    def _visit_library(self, visitor: ArtifactVisitor):
        visitor.visit_static_library(self)


class SharedLibraryArtifact(LibraryArtifact):
    def __init__(self, path: Path, *objects: ObjectArtifact) -> None:
        super().__init__(path, *objects)

    def _visit_library(self, visitor: ArtifactVisitor):
        visitor.visit_shared_library(self)


class ExecutableArtifact(Artifact):
    def __init__(self, path: Path, *dependencies: Artifact) -> None:
        super().__init__(path)
        self.deps = dependencies

    def dependencies(self) -> Iterable[Artifact]:
        return self.deps

    def accept(self, visitor: ArtifactVisitor):
        for dep in self.deps:
            dep.accept(visitor)
        visitor.visit_executable(self)


class ArtifactVisitor:
    def visit_source(self, source: SourceArtifact):
        raise NotImplementedError()

    def visit_object(self, object: ObjectArtifact):
        raise NotImplementedError()

    def visit_static_library(self, library: StaticLibraryArtifact):
        raise NotImplementedError()

    def visit_shared_library(self, library: SharedLibraryArtifact):
        raise NotImplementedError()

    def visit_executable(self, executable: ExecutableArtifact):
        raise NotImplementedError()


class BuildError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class BuildVisitor(ArtifactVisitor):
    def __init__(self) -> None:
        super().__init__()

    def __make_parent_directory(self, artifact: Artifact):
        directory = artifact.path.parent
        try:
            directory.mkdir(parents=True)
        except FileExistsError:
            return
        else:
            print(f"Created directory: {directory}")

    def __build_bin(self, artifact: Artifact, make_command: Callable[[str, str], str]):
        if not artifact.path.exists() or deps_changed(
            artifact, *artifact.dependencies()
        ):
            self.__make_parent_directory(artifact)
            deps_str = join_artifacts(*artifact.dependencies())
            command = make_command(str(artifact), deps_str)
            run_command(command)

    def visit_source(self, source: SourceArtifact):
        if not source.path.exists():
            raise BuildError(f"Source is missing: {source.path}")

    def visit_object(self, obj: ObjectArtifact):
        self.__build_bin(
            obj, lambda target, deps: f"gcc -g -Wall -o {target} -c {deps}"
        )

    def visit_static_library(self, library: StaticLibraryArtifact):
        self.__build_bin(library, lambda target, deps: f"ar rcs {target} {deps}")

    def visit_shared_library(self, library: SharedLibraryArtifact):
        self.__build_bin(
            library, lambda target, deps: f"gcc -shared -Wall -o {target} {deps}"
        )

    def visit_executable(self, executable: ExecutableArtifact):
        self.__build_bin(
            executable, lambda target, deps: f"gcc -g -Wall -o {target} {deps}"
        )


class GraphvizRootArtifact(Artifact):
    def __init__(self, path: Path, *artifacts: Artifact) -> None:
        super().__init__(path)
        self.artifacts = artifacts

    def accept(self, visitor: ArtifactVisitor):
        print("digraph {")
        for artifact in self.artifacts:
            artifact.accept(visitor)
        print("}")


class GraphvizVisitor(ArtifactVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.visited = set()

    def __node_name(self, artifact: Artifact) -> str:
        return artifact.path.name.replace(".", "_")

    def __print_node(self, artifact: Artifact):
        if not artifact in self.visited:
            print(f'  {self.__node_name(artifact)} [label="{artifact.path}"]')
            self.visited.add(artifact)

    def __print_edge(self, a: Artifact, b: Artifact):
        if not (a, b) in self.visited:
            print(f"  {self.__node_name(a)} -> {self.__node_name(b)}")
            self.visited.add((a, b))

    def visit_source(self, source: SourceArtifact):
        self.__print_node(source)

    def visit_object(self, obj: ObjectArtifact):
        self.__print_node(obj)
        self.__print_edge(obj, obj.source)

    def __visit_library(self, library: LibraryArtifact):
        self.__print_node(library)
        for obj in library.objects:
            self.__print_edge(library, obj)

    def visit_static_library(self, library: StaticLibraryArtifact):
        self.__visit_library(library)

    def visit_shared_library(self, library: SharedLibraryArtifact):
        self.__visit_library(library)

    def visit_executable(self, executable: ExecutableArtifact):
        self.__print_node(executable)
        for dep in executable.deps:
            self.__print_edge(executable, dep)


class DependencyGraph:
    def __init__(self, root_dir: Path, debug: bool = True) -> None:
        self.root_dir = root_dir
        self.src_dir = root_dir / "src"
        self.obj_dir = (
            self.root_dir / "obj" / "dbg" if debug else self.root_dir / "obj" / "rls"
        )
        self.bin_dir = self.root_dir / "bin"
        self.test_dir = self.root_dir / "test"
        self.debug = debug
        self.artifacts = {}
        self.root_artifacts: List[Artifact] = []

    def add_static_library(self, name: str, *object_names: str):
        lib = self.__get_static_library(name, *object_names)
        self.root_artifacts.append(lib)

    def add_shared_library(self, name: str, *object_names: str):
        lib = self.__get_shared_library(name, *object_names)
        self.root_artifacts.append(lib)

    def add_executable(self, name: str, *dep_names: str):
        exe = self.__get_executable(name, *dep_names)
        self.root_artifacts.append(exe)

    def accept(self, visitor: ArtifactVisitor):
        for artifact in self.root_artifacts:
            artifact.accept(visitor)

    def print_graphviz(self):
        gv_visitor = GraphvizVisitor()
        gv_root = GraphvizRootArtifact(self.root_dir, *self.root_artifacts)
        gv_root.accept(gv_visitor)

    def build(self):
        self.accept(BuildVisitor())

    def __find_source_path(self, source_name: str) -> Path:
        results = list(self.src_dir.glob(f"**/{source_name}"))
        if len(results) == 0:
            # Try test dir instead
            results = list(self.test_dir.glob(f"**/{source_name}"))
            if len(results) == 0:
                raise FileNotFoundError(f"Failed to find source file '{source_name}'")
        if len(results) > 1:
            raise FileNotFoundError(
                f"Ambiguous file pattern - found multiple source files named '{source_name}': {results}"
            )
        return results[0]

    def __lookup_artifact_or_else(
        self, name: str, op: Callable[[], Artifact]
    ) -> Artifact:
        artifact = self.artifacts.get(name)
        if not artifact:
            artifact = op()
            self.artifacts[name] = artifact
        return artifact

    def __get_source(self, name: str) -> SourceArtifact:
        def parse() -> SourceArtifact:
            path = self.__find_source_path(name)
            return SourceArtifact(path)

        return self.__lookup_artifact_or_else(name, parse)

    def __get_object(self, name: str) -> ObjectArtifact:
        def parse() -> ObjectArtifact:
            src_name = name.replace(".o", ".c")
            src = self.__get_source(src_name)
            obj_path = self.obj_dir / src.path.relative_to(self.src_dir).with_suffix(
                ".o"
            )
            return ObjectArtifact(obj_path, src)

        return self.__lookup_artifact_or_else(name, parse)

    def __get_static_library(
        self, name: str, *object_names: str
    ) -> StaticLibraryArtifact:
        def parse() -> StaticLibraryArtifact:
            lib_path = self.bin_dir / name
            objects = [self.__get_object(n) for n in object_names]
            return StaticLibraryArtifact(lib_path, *objects)

        return self.__lookup_artifact_or_else(name, parse)

    def __get_shared_library(
        self, name: str, *object_names: str
    ) -> SharedLibraryArtifact:
        def parse() -> SharedLibraryArtifact:
            lib_path = self.bin_dir / name
            objects = [self.__get_object(n) for n in object_names]
            return SharedLibraryArtifact(lib_path, *objects)

        return self.__lookup_artifact_or_else(name, parse)

    def __get_executable(self, name: str, *dep_names: str):
        def parse() -> ExecutableArtifact:
            path = self.test_dir / "bin" / name
            deps = []
            for dep_name in dep_names:
                dep = (
                    self.__get_source(dep_name)
                    if dep_name.endswith(".c")
                    else self.__get_object(dep_name)
                )
                deps.append(dep)
            return ExecutableArtifact(path, *deps)

        return self.__lookup_artifact_or_else(name, parse)


def deps_changed(target: Artifact, *dependencies: Artifact):
    for dependency in dependencies:
        if dependency.path.stat().st_mtime_ns > target.path.stat().st_mtime_ns:
            return True
    return False


def run_command(command: str):
    print(command)
    status = os.system(command) % 255
    if status != 0:
        exit(status)


def join_artifacts(*artifacts: Artifact) -> str:
    return " ".join((str(a) for a in artifacts))

