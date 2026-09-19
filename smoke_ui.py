# -*- coding: utf-8 -*-
"""v0.6 界面构建冒烟测试：实例化 Blocks，校验组件与事件绑定无错。"""
import compileall
import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
ok = compileall.compile_dir(os.path.join(root, "src"), quiet=1, maxlevels=2)
print("compileall src:", "OK" if ok else "FAIL")

import app  # noqa: E402

demo = app.build_ui()
print("build_ui OK, type:", type(demo).__name__)
print("UI smoke passed")
