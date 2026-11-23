extends Node3D
## Ce que le joueur voit.
##
## Vue "vidéo" (par défaut, réalité augmentée) :
##   1. la vidéo ENTIÈRE de la caméra est affichée en plein écran ;
##   2. le monde 3D est rendu dans une image à part (un SubViewport) au fond transparent,
##      avec une caméra 3D placée exactement comme la vraie (le tracker envoie sa position) ;
##   3. cette image 3D est posée sur la vidéo. Un petit shader (overlay.gdshader) la corrige
##      légèrement pour que le plateau tombe pile sur les 4 marqueurs de coin.
## Vues libres (touche C) : spectateur, dessus, orbite. Pas de vidéo, un sol en damier.

const VIEW_NAMES := ["vidéo (réalité augmentée)", "spectateur", "dessus", "orbite"]
const VIDEO_VIEW := 0

var game: Node3D        # main.gd (pour la taille du plateau et les conversions)
var view_index := VIDEO_VIEW

var _video_rect: TextureRect     # la vidéo, plein écran
var _video_texture: ImageTexture
var _video_size := Vector2(1280, 720)
var _overlay_material: ShaderMaterial
var _world_view: SubViewport     # le monde 3D est rendu ici...
var _camera: Camera3D            # ...par cette caméra
var _real_camera = null          # position de la vraie caméra (envoyée par le tracker), ou null
var _orbit_angle := 0.0

var _floor: MeshInstance3D       # sol opaque (vues libres)
var _shadows: MeshInstance3D     # sol invisible qui ne montre que les ombres (vue vidéo)
var _arena: MeshInstance3D       # contour de l'arène et moitié de chaque joueur


func _ready() -> void:
	# --- Le monde 3D, rendu dans sa propre image ---
	_world_view = SubViewport.new()
	_world_view.transparent_bg = true  # on verra la vidéo à travers
	_world_view.msaa_3d = Viewport.MSAA_2X
	add_child(_world_view)
	_camera = Camera3D.new()
	_world_view.add_child(_camera)  # le SubViewport voit le même monde 3D que la scène

	# --- L'écran : fond noir, vidéo, puis l'image 3D ---
	var screen := CanvasLayer.new()
	add_child(screen)
	var background := ColorRect.new()
	background.color = Color(0.015, 0.015, 0.025)
	background.set_anchors_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_child(background)

	_video_rect = _make_fullscreen_image()
	screen.add_child(_video_rect)

	# L'image 3D a les mêmes proportions que la vidéo et s'étire pareil : un point de l'une
	# est au même endroit sur l'autre.
	var overlay := _make_fullscreen_image()
	overlay.texture = _world_view.get_texture()
	_overlay_material = ShaderMaterial.new()
	_overlay_material.shader = preload("res://scripts/overlay.gdshader")
	overlay.material = _overlay_material
	screen.add_child(overlay)

	# --- Le plateau 3D : trois plans posés au même endroit ---
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_texture = _checkerboard()
	_floor = _make_plane(floor_mat, 0.0)

	var shadow_mat := StandardMaterial3D.new()
	shadow_mat.albedo_color = Color.BLACK
	shadow_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	shadow_mat.shadow_to_opacity = true  # transparent, sauf là où il y a de l'ombre
	_shadows = _make_plane(shadow_mat, 0.002)

	var arena_mat := StandardMaterial3D.new()
	arena_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	arena_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	arena_mat.albedo_texture = _arena_drawing()
	arena_mat.render_priority = 1  # toujours dessiné après les ombres
	_arena = _make_plane(arena_mat, 0.01)

	set_board_size(game.board_cm)
	_camera.transform = _free_camera_transform(1)


func _make_fullscreen_image() -> TextureRect:
	var r := TextureRect.new()
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED  # remplit l'écran sans déformer
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


func _make_plane(mat: Material, height: float) -> MeshInstance3D:
	var plane := MeshInstance3D.new()
	plane.mesh = PlaneMesh.new()
	plane.mesh.material = mat
	plane.position.y = height
	add_child(plane)
	return plane


## Damier vert pour le sol des vues libres.
func _checkerboard() -> ImageTexture:
	var img := Image.create_empty(600, 400, false, Image.FORMAT_RGB8)
	img.fill(Color(0.12, 0.2, 0.14))
	var line := Color(0.2, 0.3, 0.22)
	for i in range(0, 600, 50):
		img.fill_rect(Rect2i(i, 0, 2, 400), line)
	for j in range(0, 400, 50):
		img.fill_rect(Rect2i(0, j, 600, 2), line)
	return ImageTexture.create_from_image(img)


## Contour blanc, ligne du milieu, et une légère teinte bleue (joueur 1) / rouge (joueur 2).
func _arena_drawing() -> ImageTexture:
	var w := 600
	var h := 400
	var img := Image.create_empty(w, h, false, Image.FORMAT_RGBA8)
	img.fill_rect(Rect2i(0, 0, w / 2, h), Color(0.25, 0.5, 1.0, 0.10))
	img.fill_rect(Rect2i(w / 2, 0, w / 2, h), Color(1.0, 0.3, 0.25, 0.10))
	var white := Color(1, 1, 1, 0.85)
	img.fill_rect(Rect2i(0, 0, w, 4), white)
	img.fill_rect(Rect2i(0, h - 4, w, 4), white)
	img.fill_rect(Rect2i(0, 0, 4, h), white)
	img.fill_rect(Rect2i(w - 4, 0, 4, h), white)
	img.fill_rect(Rect2i(w / 2 - 1, 0, 3, h), Color(1, 1, 1, 0.5))
	img.generate_mipmaps()  # reste net quand l'arène est vue de loin
	return ImageTexture.create_from_image(img)


# ============================================================ appelé par main.gd
func set_board_size(size_cm: Vector2) -> void:
	for plane in [_floor, _shadows, _arena]:
		plane.mesh.size = size_cm * game.CM


func show_video(image: Image) -> void:
	if _video_texture != null and Vector2(image.get_size()) == _video_size:
		_video_texture.update(image)  # même taille : on remplace juste les pixels (rapide)
	else:
		_video_texture = ImageTexture.create_from_image(image)
		_video_rect.texture = _video_texture
		_video_size = Vector2(image.get_size())


func set_real_camera(camera) -> void:
	_real_camera = camera if camera is Dictionary else null


func next_view() -> void:
	view_index = (view_index + 1) % VIEW_NAMES.size()


func view_name() -> String:
	return VIEW_NAMES[view_index]


# ============================================================ chaque image
func _process(delta: float) -> void:
	# L'image 3D a les proportions de la vidéo, à la taille où la vidéo est affichée.
	var screen_size := get_viewport().get_visible_rect().size
	var zoom := maxf(screen_size.x / _video_size.x, screen_size.y / _video_size.y)
	_world_view.size = Vector2i((_video_size * zoom).round())

	var video_view := view_index == VIDEO_VIEW
	_video_rect.visible = video_view
	_world_view.transparent_bg = video_view
	_shadows.visible = video_view
	_floor.visible = not video_view
	_camera.cull_mask = 0xFFFFF  # tout voir

	if video_view:
		if _real_camera == null:
			_camera.cull_mask = 0  # plateau pas encore trouvé : on montre juste la vidéo
		else:
			_copy_real_camera()
	else:
		_camera.fov = 50.0
		_set_correction([1, 0, 0, 0, 1, 0, 0, 0, 1])  # pas de correction
		_orbit_angle += delta * 0.25
		# On glisse doucement vers la position de la vue choisie.
		var target := _free_camera_transform(view_index)
		_camera.transform = _camera.transform.interpolate_with(target, 1.0 - exp(-3.0 * delta))


## Place la caméra 3D exactement comme la vraie caméra.
## Le tracker utilise les axes d'OpenCV : x droite, y bas, z vers l'avant, et un repère
## plateau où z descend dans la table. Godot : X droite, Y haut, la caméra regarde vers -Z.
func _copy_real_camera() -> void:
	var c: Dictionary = _real_camera
	var right := _plateau_direction(c["right"])
	var up := -_plateau_direction(c["down"])
	var backward := -_plateau_direction(c["forward"])
	var p: Array = c["pos"]
	var position_3d: Vector3 = game.board_to_world(Vector2(p[0], p[1]), -p[2] * game.CM)
	_camera.transform = Transform3D(Basis(right, up, backward).orthonormalized(), position_3d)
	_camera.keep_aspect = Camera3D.KEEP_HEIGHT
	_camera.fov = c["fov_y"]
	_set_correction(c["warp"])


## Direction dans le repère du plateau (x, y, z vers le bas) -> direction Godot.
func _plateau_direction(v: Array) -> Vector3:
	return Vector3(v[0], -v[2], v[1])


## La correction du shader : une matrice 3 x 3, donnée ligne par ligne.
func _set_correction(m: Array) -> void:
	_overlay_material.set_shader_parameter("row0", Vector3(m[0], m[1], m[2]))
	_overlay_material.set_shader_parameter("row1", Vector3(m[3], m[4], m[5]))
	_overlay_material.set_shader_parameter("row2", Vector3(m[6], m[7], m[8]))


func _free_camera_transform(view: int) -> Transform3D:
	var w: float = game.board_cm.x * game.CM
	match view:
		1:  # spectateur, un peu en hauteur
			return Transform3D.IDENTITY.translated(Vector3(0, w * 0.72, w * 0.7)).looking_at(Vector3(0, 0, 0.6))
		2:  # vue de dessus
			return Transform3D(Basis.from_euler(Vector3(-PI / 2, 0, 0)), Vector3(0, w * 0.9, 0))
		_:  # orbite lente autour du plateau
			var p := Vector3(sin(_orbit_angle) * w * 0.85, w * 0.42, cos(_orbit_angle) * w * 0.85)
			return Transform3D.IDENTITY.translated(p).looking_at(Vector3.ZERO)
