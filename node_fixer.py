"""
节点修复工具
从 fix_node/fix_node.blend 中加载正常节点组，并替换损坏的节点组节点
支持：
  - 修复当前选中的节点
  - 一键修复当前文件中所有材质、世界及节点组内部的目标问题节点
"""
import bpy
import os

# ==================== 配置 ====================
TARGET_GROUP_NAMES = [
    "Surface Curvature",
    "Shading Models",
    "Kuwahara",
    "Cavity",
    "Co-Planar Edge Detection",
    "Curvature",
    "Shader Info",
]


def get_fix_blend_path():
    """返回 fix_node.blend 的完整路径（位于插件目录下的 fix_node 文件夹中）"""
    return os.path.join(os.path.dirname(__file__), "fix_node", "fix_node.blend")


def load_clean_group_template(group_name):
    """
    从 fix_node.blend 追加一个指定名称的节点组。
    返回加载进来的、与 group_name 匹配的节点组数据块（忽略自动追加的子节点组）。
    """
    path = get_fix_blend_path()
    if not os.path.exists(path):
        print(f"❌ Fix file not found: {path}")
        return None

    existing_names = set(bpy.data.node_groups.keys())

    with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
        if group_name not in data_from.node_groups:
            print(f"❌ Node group '{group_name}' not found in fix blend file")
            return None
        data_to.node_groups = [group_name]

    # 找到新加载的并匹配名称的节点组
    for ng in bpy.data.node_groups:
        if ng.name not in existing_names:
            base = ng.name.split('.')[0]
            if base == group_name:
                print(f"  成功匹配模板: {ng.name}")
                return ng

    for ng in bpy.data.node_groups:
        if ng.name not in existing_names:
            if ng.name.startswith(group_name):
                print(f"  模糊匹配模板: {ng.name}")
                return ng

    print(f"❌ Unable to identify loaded node group: {group_name}")
    return None


def get_corresponding_socket(old_node, old_socket, new_node, is_output):
    """根据索引在新节点上找到对应的端口"""
    old_sockets = old_node.outputs if is_output else old_node.inputs
    new_sockets = new_node.outputs if is_output else new_node.inputs
    for i, sock in enumerate(old_sockets):
        if sock == old_socket:
            if i < len(new_sockets):
                return new_sockets[i]
    return None


def replace_single_node(node_tree, old_node, template, suffix="fixed"):
    """在给定的 node_tree 中，用 template 的独立副本替换 old_node，返回新创建的节点"""
    new_group = template.copy()
    new_group.name = f"{template.name.split('.')[0]}_{suffix}_{old_node.name}"
    print(f"  创建独立副本: {new_group.name}")

    new_node = node_tree.nodes.new(type='ShaderNodeGroup')
    new_node.node_tree = new_group

    # 复制属性
    skip = {'rna_type', 'type', 'name', 'location', 'dimensions',
            'inputs', 'outputs', 'internal_links', 'interface', 'node_tree'}
    for prop in old_node.bl_rna.properties:
        if prop.is_readonly or prop.identifier in skip:
            continue
        try:
            setattr(new_node, prop.identifier, getattr(old_node, prop.identifier))
        except:
            pass

    if hasattr(old_node, 'use_custom_color') and old_node.use_custom_color:
        try:
            new_node.use_custom_color = True
            new_node.color = old_node.color
        except:
            pass

    # 输入端口默认值
    for i, inp in enumerate(old_node.inputs):
        if i >= len(new_node.inputs):
            break
        new_inp = new_node.inputs[i]
        if hasattr(inp, 'default_value') and hasattr(new_inp, 'default_value'):
            try:
                new_inp.default_value = inp.default_value
            except:
                pass

    new_node.location = old_node.location
    new_node.location.x += 200
    return new_node


def transfer_links_and_cleanup(node_tree, old_to_new):
    """转移连线并删除旧节点"""
    links_to_remove = []
    links_to_create = []
    for link in node_tree.links:
        from_node = link.from_node
        to_node = link.to_node
        from_sock = link.from_socket
        to_sock = link.to_socket

        new_from = old_to_new.get(from_node, from_node)
        new_to = old_to_new.get(to_node, to_node)

        if new_from != from_node or new_to != to_node:
            from_sock_new = get_corresponding_socket(from_node, from_sock, new_from, True) if new_from != from_node else from_sock
            to_sock_new = get_corresponding_socket(to_node, to_sock, new_to, False) if new_to != to_node else to_sock
            if from_sock_new and to_sock_new:
                links_to_create.append((from_sock_new, to_sock_new))
                links_to_remove.append(link)

    for from_sock, to_sock in links_to_create:
        try:
            node_tree.links.new(from_sock, to_sock)
        except Exception as e:
            print(f"  连线失败: {e}")

    for link in links_to_remove:
        try:
            node_tree.links.remove(link)
        except:
            pass

    for old_node in old_to_new.keys():
        node_tree.nodes.remove(old_node)


def collect_all_node_trees():
    """
    收集当前文件中所有需要检查的节点树（包含嵌套）
    返回列表，每项为 (描述, node_tree)
    """
    trees = []

    # 材质节点树
    for mat in bpy.data.materials:
        if mat.node_tree:
            trees.append((f"材质: {mat.name}", mat.node_tree))

    # 世界节点树
    world = bpy.context.scene.world
    if world and world.node_tree:
        trees.append((f"世界: {world.name}", world.node_tree))

    # 所有自定义节点组（它们自己也是节点树）
    for group in bpy.data.node_groups:
        # 节点组本身就是 node_tree
        trees.append((f"节点组: {group.name}", group))

    return trees


# ==================== 操作符：修复选中 ====================
class NODE_OT_fix_selected_nodes(bpy.types.Operator):
    bl_idname = "node.fix_selected_nodes"
    bl_label = "修复选中的节点"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node_tree = None
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                space = area.spaces.active
                if space and space.edit_tree:
                    node_tree = space.edit_tree
                    break
        if not node_tree:
            self.report({'ERROR'}, "请打开节点编辑器并选中一个节点树")
            return {'CANCELLED'}

        selected = [n for n in node_tree.nodes if n.select and n.type == 'GROUP']
        if not selected:
            self.report({'WARNING'}, "没有选中任何节点组节点")
            return {'CANCELLED'}

        replaced = 0
        loaded_templates = {}
        old_to_new = {}

        for old_node in selected:
            if not old_node.node_tree:
                continue
            base_name = old_node.node_tree.name.split('.')[0]
            if base_name not in TARGET_GROUP_NAMES:
                continue

            if base_name not in loaded_templates:
                template = load_clean_group_template(base_name)
                if template is None:
                    continue
                loaded_templates[base_name] = template
            template = loaded_templates[base_name]

            new_node = replace_single_node(node_tree, old_node, template, suffix="fixed")
            if new_node:
                old_to_new[old_node] = new_node
                replaced += 1

        if replaced == 0:
            self.report({'INFO'}, "没有需要修复的节点（可能不在列表中）")
            return {'CANCELLED'}

        transfer_links_and_cleanup(node_tree, old_to_new)

        for n in node_tree.nodes:
            n.select = False
        for n in old_to_new.values():
            n.select = True
        node_tree.nodes.active = next(iter(old_to_new.values())) if old_to_new else None

        self.report({'INFO'}, f"成功修复 {replaced} 个节点")
        return {'FINISHED'}


# ==================== 操作符：一键修复所有节点（包括嵌套） ====================
class NODE_OT_fix_all_nodes(bpy.types.Operator):
    bl_idname = "node.fix_all_nodes"
    bl_label = "一键修复所有材质中的问题节点（包含嵌套）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        all_trees = collect_all_node_trees()
        total_replaced = 0
        loaded_templates = {}

        for desc, node_tree in all_trees:
            # 收集此节点树中需要替换的节点
            nodes_to_fix = []
            for node in node_tree.nodes:
                if node.type == 'GROUP' and node.node_tree:
                    base_name = node.node_tree.name.split('.')[0]
                    if base_name in TARGET_GROUP_NAMES:
                        nodes_to_fix.append(node)

            if not nodes_to_fix:
                continue

            print(f"正在处理: {desc}，找到 {len(nodes_to_fix)} 个问题节点")
            old_to_new = {}
            for old_node in nodes_to_fix:
                base_name = old_node.node_tree.name.split('.')[0]
                # 加载模板
                if base_name not in loaded_templates:
                    template = load_clean_group_template(base_name)
                    if template is None:
                        print(f"  跳过 {base_name}，无法加载模板")
                        continue
                    loaded_templates[base_name] = template
                template = loaded_templates[base_name]

                new_node = replace_single_node(node_tree, old_node, template, suffix="all_fix")
                if new_node:
                    old_to_new[old_node] = new_node
                    total_replaced += 1

            # 在节点树内部执行连线转移和清理
            transfer_links_and_cleanup(node_tree, old_to_new)

        self.report({'INFO'}, f"完成，共修复 {total_replaced} 个节点（含嵌套）")
        return {'FINISHED'}


# ==================== 面板 ====================
class VIEW3D_PT_node_fixer(bpy.types.Panel):
    bl_label = "NPR节点修复工具"
    bl_idname = "VIEW3D_PT_node_fixer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "风格化材质"
    bl_parent_id = "VIEW3D_PT_custom_nodes"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("node.fix_selected_nodes", text="仅修复选中的节点", icon='RESTRICT_SELECT_OFF')
        layout.operator("node.fix_all_nodes", text="一键修复全部NPR节点", icon='TOOL_SETTINGS')
        layout.separator()


# ==================== 类列表 ====================
classes = [
    NODE_OT_fix_selected_nodes,
    NODE_OT_fix_all_nodes,
    VIEW3D_PT_node_fixer,
]