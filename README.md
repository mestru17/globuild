# globuild
globuild is an easy and opinionated build automation tool for C projects. It uses [glob](https://en.wikipedia.org/wiki/Glob_(programming)) patterns to recursively find dependencies, so that developers don't have to specify the full (relative) paths to dependencies when defining artifacts to build.

## Example
Let's say that you have are developing a C library containing implementations of common data structures and you're project structure is as follows:
```bash
.
├── src
│  ├── llist
│  │  ├── llist.c
│  │  └── llist.h
│  └── vector
│     ├── vector.c
│     └── vector.h
└── build.py
```

You want to build both a static and shared library containing the object code of `llist.c` and `vector.c`. In your `build.py` you put:
```python
#!/usr/bin/env python3
from globuild import DependencyGraph
from pathlib import Path

dg = DependencyGraph(Path())
dg.add_static_library("libds.a", "llist.o", "vector.o")
dg.add_shared_library("libds.so", "llist.o", "vector.o")
dg.build()
```

You then just run `build.py` which is going to automatically find the sources corresponding to the `.o` files, generate a dependency graph and then build all missing or new files the same way that make would:
```bash
$ python3 build.py
Created directory: obj/dbg/llist
gcc -g -Wall -o obj/dbg/llist/llist.o -c src/llist/llist.c
Created directory: obj/dbg/vector
gcc -g -Wall -o obj/dbg/vector/vector.o -c src/vector/vector.c
Created directory: bin
ar rcs bin/libds.a obj/dbg/llist/llist.o obj/dbg/vector/vector.o
gcc -shared -Wall -o bin/libds.so obj/dbg/llist/llist.o obj/dbg/vector/vector.o
```

Afterwards your libraries should have been compiled to the `bin` directory:
```bash
.
├── bin
│  ├── libds.a
│  └── libds.so
├── obj
│  └── dbg
│     ├── llist
│     │  └── llist.o
│     └── vector
│        └── vector.o
├── src
│  ├── llist
│  │  ├── llist.c
│  │  └── llist.h
│  └── vector
│     ├── vector.c
│     └── vector.h
└── build.py
```

Running `build.py` again works like Make - i.e. nothing will happen because there has been no changes to any of the files in the dependency graph.

It is also possible to get a visualization of the dependency graph in the form of Graphviz source code by using `dg.print_graphviz()`:
```bash
digraph {
  llist_c [label="src/llist/llist.c"]
  llist_o [label="obj/dbg/llist/llist.o"]
  llist_o -> llist_c
  vector_c [label="src/vector/vector.c"]
  vector_o [label="obj/dbg/vector/vector.o"]
  vector_o -> vector_c
  libds_a [label="bin/libds.a"]
  libds_a -> llist_o
  libds_a -> vector_o
  libds_so [label="bin/libds.so"]
  libds_so -> llist_o
  libds_so -> vector_o
}
```

Using a Graphviz renderer, you would then be able to see: (PLACEHOLDER)
