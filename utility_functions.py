"""
实用功能模块
包含空物体整理、命名管理等实用工具
"""

import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty, EnumProperty

# ==================== 配置区域 ====================
MATERIAL_SUFFIX = "_Material"
DEFAULT_SEPARATOR = "_"


# ==================== 3D视图侧边栏面板 ====================
class VIEW3D_PT_utility(Panel):
    bl_label = "实用功能"
    bl_idname = "VIEW3D_PT_utility"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "风格化材质"
    bl_parent_id = "VIEW3D_PT_custom_nodes"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        pass


class VIEW3D_PT_empty_management(Panel):
    bl_label = "空物体整理"
    bl_idname = "VIEW3D_PT_empty_management"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "风格化材质"
    bl_parent_id = "VIEW3D_PT_utility"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("object.move_child_empties_to_collection", text="子级空物体到集合", icon='EMPTY_DATA')
        row.operator("object.move_child_empties_to_related", text="子级空物体移至关联集合", icon='LINKED')
        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("object.move_parent_empties_to_collection", text="父级空物体到集合", icon='GROUP')
        row.operator("object.move_parent_empties_to_related", text="父级空物体移至关联集合", icon='LINKED')


class VIEW3D_PT_naming_management(Panel):
    bl_label = "命名管理"
    bl_idname = "VIEW3D_PT_naming_management"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "风格化材质"
    bl_parent_id = "VIEW3D_PT_utility"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        # 材质 ↔ 物体
        box = layout.box()
        box.label(text="材质 ↔ 物体", icon='MATERIAL')
        row = box.row(align=True)
        row.operator("object.rename_materials_by_object", text="材质→物体名+后缀", icon='MATERIAL_DATA')
        row.operator("object.rename_object_by_material", text="物体→材质名前缀", icon='OBJECT_DATA')
        row = box.row(align=True)
        row.label(text="提示：材质重命名默认后缀为 _Material", icon='INFO')

        layout.separator(factor=0.5)

        # 集合对象批量重命名（按序号）
        box = layout.box()
        box.label(text="集合对象重命名（按序号）", icon='OUTLINER_COLLECTION')
        row = box.row(align=True)
        row.prop(context.scene, "rename_collection_selector", text="目标集合")
        row = box.row(align=True)
        row.prop(context.scene, "rename_separator", text="分隔符")
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("object.rename_collection_objects", text="执行重命名", icon='OUTLINER_OB_GROUP_INSTANCE')


# ==================== 场景属性（用于UI存储用户选择） ====================
def get_collection_items(self, context):
    items = []
    items.append(("ALL", "所有集合", "对每个集合分别重命名其内部对象（独立编号）"))
    for coll in bpy.data.collections:
        items.append((coll.name, coll.name, f"重命名集合 '{coll.name}' 中的所有对象"))
    return items

def update_separator(self, context):
    pass

def register_scene_properties():
    bpy.types.Scene.rename_collection_selector = EnumProperty(
        name="集合",
        items=get_collection_items,
        description="选择要操作的集合"
    )
    bpy.types.Scene.rename_separator = StringProperty(
        name="分隔符",
        default=DEFAULT_SEPARATOR,
        description="集合名与编号之间的分隔符",
        maxlen=5,
        update=update_separator
    )

def unregister_scene_properties():
    if hasattr(bpy.types.Scene, "rename_collection_selector"):
        del bpy.types.Scene.rename_collection_selector
    if hasattr(bpy.types.Scene, "rename_separator"):
        del bpy.types.Scene.rename_separator


# ==================== 命名管理操作符 ====================
class OBJECT_OT_rename_materials_by_object(Operator):
    """将选中物体的所有材质重命名为"物体名+后缀"格式"""
    bl_idname = "object.rename_materials_by_object"
    bl_label = "材质重命名为物体名+后缀"
    bl_description = "将当前选中物体的所有材质重命名为“物体名 + 通用后缀”"
    bl_options = {'REGISTER', 'UNDO'}

    suffix: StringProperty(
        name="后缀",
        default=MATERIAL_SUFFIX,
        description="材质名称后缀，如 _Material"
    )

    def execute(self, context):
        selected_objs = context.selected_objects
        if not selected_objs:
            self.report({'WARNING'}, "请至少选中一个物体")
            return {'CANCELLED'}

        renamed_count = 0
        for obj in selected_objs:
            if obj.type != 'MESH':
                continue
            if not obj.data.materials:
                continue
            for slot in obj.material_slots:
                if slot.material:
                    new_name = f"{obj.name}{self.suffix}"
                    original_new_name = new_name
                    counter = 1
                    while new_name in bpy.data.materials and bpy.data.materials[new_name] != slot.material:
                        new_name = f"{original_new_name}_{counter:02d}"
                        counter += 1
                    if slot.material.name != new_name:
                        slot.material.name = new_name
                        renamed_count += 1
        self.report({'INFO'}, f"已将 {renamed_count} 个材质重命名为“物体名{self.suffix}”格式")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class OBJECT_OT_rename_object_by_material(Operator):
    """将选中物体的名称改为其活动材质名称的第一个下划线之前的部分"""
    bl_idname = "object.rename_object_by_material"
    bl_label = "物体重命名为材质名前缀"
    bl_description = "将当前选中物体的名称改为其活动材质名称的第一个下划线之前的部分"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objs = context.selected_objects
        if not selected_objs:
            self.report({'WARNING'}, "请至少选中一个物体")
            return {'CANCELLED'}

        renamed_count = 0
        for obj in selected_objs:
            if obj.type != 'MESH':
                continue
            mat = obj.active_material
            if mat is None and obj.material_slots:
                mat = obj.material_slots[0].material
            if mat is None:
                self.report({'WARNING'}, f"物体 {obj.name} 没有材质，跳过")
                continue

            mat_name = mat.name
            if '_' in mat_name:
                prefix = mat_name.split('_')[0]
            else:
                prefix = mat_name

            if obj.name != prefix:
                original_prefix = prefix
                counter = 1
                while prefix in bpy.data.objects and bpy.data.objects[prefix] != obj:
                    prefix = f"{original_prefix}_{counter:02d}"
                    counter += 1
                obj.name = prefix
                renamed_count += 1
        self.report({'INFO'}, f"已将 {renamed_count} 个物体重命名为材质名前缀")
        return {'FINISHED'}


class OBJECT_OT_rename_collection_objects(Operator):
    """将指定集合中的所有对象重命名为“集合名+分隔符+三位序号”（如 地面_001），自动处理重名"""
    bl_idname = "object.rename_collection_objects"
    bl_label = "批量重命名集合内对象（序号）"
    bl_description = "将集合内所有对象按序号重命名，格式：集合名_001"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = context.scene.rename_collection_selector
        separator = context.scene.rename_separator
        if not separator:
            separator = DEFAULT_SEPARATOR

        if target == "ALL":
            collections_to_process = list(bpy.data.collections)
        else:
            coll = bpy.data.collections.get(target)
            if coll is None:
                self.report({'ERROR'}, f"找不到集合 '{target}'")
                return {'CANCELLED'}
            collections_to_process = [coll]

        total_renamed = 0
        for coll in collections_to_process:
            renamed = self.rename_collection_objects(coll, separator)
            if renamed:
                self.report({'INFO'}, f"集合 '{coll.name}': 已重命名 {renamed} 个对象")
            total_renamed += renamed

        if total_renamed == 0:
            self.report({'WARNING'}, "没有需要重命名的对象（集合可能为空或命名已符合）")
        else:
            self.report({'INFO'}, f"总计重命名 {total_renamed} 个对象")
        return {'FINISHED'}

    def rename_collection_objects(self, collection, separator):
        """对单个集合执行按序号重命名，返回成功数量"""
        objects = list(collection.objects)
        if not objects:
            return 0

        # 按名称排序，确保编号顺序可预测
        objects.sort(key=lambda o: o.name)

        used_names = set(bpy.data.objects.keys())
        rename_map = {}
        counter = 1
        for obj in objects:
            # 生成基础名称：集合名 + 分隔符 + 三位序号
            base_name = f"{collection.name}{separator}{counter:03d}"
            new_name = base_name
            # 解决全局重名冲突
            while new_name in used_names and (new_name != obj.name or bpy.data.objects.get(new_name) != obj):
                counter += 1
                new_name = f"{collection.name}{separator}{counter:03d}"
            if new_name == obj.name:
                # 名称已经正确，无需重命名，但计数器依然推进（避免重复序号）
                counter += 1
                continue
            rename_map[obj] = new_name
            used_names.add(new_name)
            counter += 1

        # 执行重命名
        renamed_count = 0
        for obj, new_name in rename_map.items():
            obj.name = new_name
            renamed_count += 1
        return renamed_count


# ==================== 空物体整理辅助函数 ====================
def ensure_empty_collections(subcoll_name):
    parent_name = "场景所有空物体"
    parent = bpy.data.collections.get(parent_name)
    if parent is None:
        parent = bpy.data.collections.new(parent_name)
        bpy.context.scene.collection.children.link(parent)
    else:
        if parent.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(parent)

    sub = bpy.data.collections.get(subcoll_name)
    if sub is None:
        sub = bpy.data.collections.new(subcoll_name)
        parent.children.link(sub)
    else:
        if sub.name not in parent.children:
            for coll in bpy.data.collections:
                if sub.name in coll.children:
                    coll.children.unlink(sub)
            parent.children.link(sub)
    return sub


# ==================== 空物体整理操作符 ====================
class OBJECT_OT_move_child_empties_to_collection(Operator):
    """将所有子级空物体移动到"子级空物体"集合中"""
    bl_idname = "object.move_child_empties_to_collection"
    bl_label = "子级空物体到集合"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_coll = ensure_empty_collections("子级空物体")
        moved = 0
        for obj in bpy.data.objects:
            if obj.type == 'EMPTY' and obj.parent is not None:
                for coll in list(obj.users_collection):
                    coll.objects.unlink(obj)
                target_coll.objects.link(obj)
                moved += 1
        self.report({'INFO'}, f"已将 {moved} 个子级空物体移至“子级空物体”集合")
        return {'FINISHED'}


class OBJECT_OT_move_child_empties_to_related(Operator):
    """将所有子级空物体移动到其父物体所在的集合"""
    bl_idname = "object.move_child_empties_to_related"
    bl_label = "子级空物体移至关联集合"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        moved = 0
        for obj in bpy.data.objects:
            if obj.type == 'EMPTY' and obj.parent is not None:
                parent_colls = obj.parent.users_collection
                if not parent_colls:
                    continue
                target = parent_colls[0]
                for coll in list(obj.users_collection):
                    coll.objects.unlink(obj)
                target.objects.link(obj)
                moved += 1
        self.report({'INFO'}, f"已将 {moved} 个子级空物体移至其父物体所在集合")
        return {'FINISHED'}


class OBJECT_OT_move_parent_empties_to_collection(Operator):
    """将所有父级空物体（无父物体且有子物体）移动到"父级空物体"集合中"""
    bl_idname = "object.move_parent_empties_to_collection"
    bl_label = "父级空物体到集合"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_coll = ensure_empty_collections("父级空物体")
        moved = 0
        for obj in bpy.data.objects:
            if obj.type == 'EMPTY' and obj.parent is None and obj.children:
                for coll in list(obj.users_collection):
                    coll.objects.unlink(obj)
                target_coll.objects.link(obj)
                moved += 1
        self.report({'INFO'}, f"已将 {moved} 个父级空物体移至“父级空物体”集合")
        return {'FINISHED'}


class OBJECT_OT_move_parent_empties_to_related(Operator):
    """将所有父级空物体移动到其第一个子物体所在的集合"""
    bl_idname = "object.move_parent_empties_to_related"
    bl_label = "父级空物体移至关联集合"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        moved = 0
        for obj in bpy.data.objects:
            if obj.type == 'EMPTY' and obj.parent is None and obj.children:
                first_child = sorted(obj.children, key=lambda c: c.name)[0]
                child_colls = first_child.users_collection
                if not child_colls:
                    continue
                target = child_colls[0]
                for coll in list(obj.users_collection):
                    coll.objects.unlink(obj)
                target.objects.link(obj)
                moved += 1
        self.report({'INFO'}, f"已将 {moved} 个父级空物体移至其第一个子物体所在集合")
        return {'FINISHED'}


# ==================== 类列表 ====================
classes = [
    VIEW3D_PT_utility,
    VIEW3D_PT_empty_management,
    VIEW3D_PT_naming_management,
    OBJECT_OT_rename_materials_by_object,
    OBJECT_OT_rename_object_by_material,
    OBJECT_OT_rename_collection_objects,
    OBJECT_OT_move_child_empties_to_collection,
    OBJECT_OT_move_child_empties_to_related,
    OBJECT_OT_move_parent_empties_to_collection,
    OBJECT_OT_move_parent_empties_to_related,
]