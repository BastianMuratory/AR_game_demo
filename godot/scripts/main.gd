extends Node3D
## Scène principale : les règles du jeu.
## Reçoit l'état envoyé par tracker.py (position des cartes) et fait réagir le jeu.
##
## Ce que le joueur VOIT (vidéo plein écran, caméra 3D alignée, vues libres) est dans view.gd.
##
## Repère : le tracker donne des positions en cm sur le plateau
##   (0, 0) = coin haut-gauche, x vers la droite, y vers le bas.
## Dans Godot : x plateau -> axe X, y plateau -> axe Z, la hauteur -> axe Y.
## Un angle de carte est en degrés : 0 = vers la droite, 90 = vers le bas.

const NetClient := preload("res://scripts/net_client.gd")
const View := preload("res://scripts/view.gd")
const Models := preload("res://scripts/models.gd")
const FX := preload("res://scripts/fx.gd")

## Les scènes des objets du jeu. Chacune contient un modèle 3D de res://models/ (fichier .glb).
## Pour changer l'apparence d'un objet, modifie son .glb dans Blender (voir README).
const BaseScene := preload("res://scenes/base.tscn")
const TowerScene := preload("res://scenes/tour.tscn")
const FireballScene := preload("res://scenes/boule_de_feu.tscn")
const MarkerScene := preload("res://scenes/anneau.tscn")

## Unités Godot par cm de plateau (un plateau de 60 x 40 cm fait 12 x 8 unités).
const CM := 0.2
## Position des bases pour la touche B (test sans cartes) : distance au bord gauche/droit (cm).
const FORTRESS_INSET_CM := 6.0

var board_cm := Vector2(60, 40)  # taille du plateau, mise à jour par le tracker
var families: Array = []         # familles de cartes lues dans cards.json
var fortresses: Array = []       # bases : [0] = joueur 1 (moitié gauche), [1] = joueur 2 (moitié droite)
var game_over := false
var view: Node3D                 # l'affichage (view.gd)

var _net: Node
var _cards := {}                 # id de carte -> {"marker": anneau, "mats": matériaux de l'anneau, "placed": jouée ?, "spawned": objet créé}
var _calibrated := false
var _status_label: Label
var _banner_label: Label


# ============================================================ démarrage
func _ready() -> void:
	families = JSON.parse_string(FileAccess.get_file_as_string("res://cards.json"))["families"]
	_add_light()

	view = View.new()
	view.game = self
	add_child(view)

	for player in 2:
		_add_fortress(player)
	_build_hud()

	_net = NetClient.new()
	add_child(_net)
	_net.state_received.connect(_on_state)
	_net.frame_received.connect(view.show_video)


func _add_light() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.015, 0.015, 0.025)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.65, 0.65, 0.75)
	env.ambient_light_energy = 0.45
	env.glow_enabled = true  # fait briller les sorts
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -30, 0)
	sun.light_energy = 1.1
	sun.shadow_enabled = true
	add_child(sun)


## Les bases existent dès le début mais restent invisibles tant que leur carte n'est pas posée.
func _add_fortress(player: int) -> void:
	var f: Node3D = BaseScene.instantiate()
	f.player = player
	f.color = Color(0.25, 0.5, 1.0) if player == 0 else Color(1.0, 0.3, 0.25)
	add_child(f)
	f.destroyed.connect(_on_fortress_destroyed)
	fortresses.append(f)


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 1  # par-dessus l'image du jeu
	add_child(layer)

	_status_label = _make_label(20)
	_status_label.position = Vector2(16, 12)
	layer.add_child(_status_label)

	var help := _make_label(16)
	help.text = "C : changer de vue (vidéo / 3D)   ·   R : rejouer   ·   B : bases de test   ·   F / G : boule de feu de test (J1 / J2)"
	help.anchor_top = 1.0  # collé en bas de l'écran
	help.anchor_bottom = 1.0
	help.offset_left = 16
	help.offset_top = -38
	layer.add_child(help)

	_banner_label = _make_label(64)
	_banner_label.set_anchors_preset(Control.PRESET_FULL_RECT)
	_banner_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	layer.add_child(_banner_label)


## Un texte blanc avec un contour noir, lisible sur la vidéo.
func _make_label(size: int) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", maxi(4, size / 4))
	return l


# ============================================================ conversions plateau <-> monde 3D
## Point du plateau (cm) -> position dans le monde Godot. Le centre du plateau est en (0, 0, 0).
func board_to_world(p: Vector2, height := 0.0) -> Vector3:
	return Vector3((p.x - board_cm.x / 2) * CM, height, (p.y - board_cm.y / 2) * CM)


## Angle d'une carte -> direction dans le monde Godot.
func angle_to_direction(angle_deg: float) -> Vector3:
	var a := deg_to_rad(angle_deg)
	return Vector3(cos(a), 0.0, sin(a))


## Le joueur qui possède cette moitié du plateau (0 = gauche, 1 = droite).
func owner_of(p: Vector2) -> int:
	return 0 if p.x < board_cm.x / 2 else 1


## Vrai si une position du monde est sortie du plateau (avec une marge).
func is_outside(p: Vector3, margin := 1.0) -> bool:
	return absf(p.x) > board_cm.x * CM / 2 + margin or absf(p.z) > board_cm.y * CM / 2 + margin


## Position par défaut d'une base (touche B, ou boules de feu de test).
func fortress_position(player: int) -> Vector3:
	var x := FORTRESS_INSET_CM if player == 0 else board_cm.x - FORTRESS_INSET_CM
	return board_to_world(Vector2(x, board_cm.y / 2))


func _set_board_size(size_cm: Vector2) -> void:
	board_cm = size_cm
	view.set_board_size(size_cm)


func _family_of(id: int) -> Dictionary:
	for f in families:
		if id >= f["first_id"] and id < f["first_id"] + f["count"]:
			return f
	return {}


# ============================================================ messages du tracker
func _on_state(state: Dictionary) -> void:
	_calibrated = state.get("calibrated", false)
	view.set_real_camera(state.get("camera"))

	# Taille du plateau mesurée par le tracker.
	var b = state.get("board")
	if b is Dictionary:
		var size := Vector2(b["w"], b["h"])
		if size.x > 1 and size.y > 1 and not size.is_equal_approx(board_cm):
			_set_board_size(size)

	# Cartes vues sur la table.
	var seen := {}
	for c in state.get("cards", []):
		var id := int(c["id"])
		var pos := Vector2(c["x"], c["y"])
		var angle: float = c["angle"]
		seen[id] = true
		if not _cards.has(id):  # nouvelle carte : on lui crée son anneau de charge
			_cards[id] = _make_marker(id)
		var card: Dictionary = _cards[id]
		_update_marker(card, pos, angle, c["progress"])
		if c["stable"] and not card["placed"]:
			card["placed"] = true
			card["spawned"] = _on_card_played(id, pos, angle)
		elif card["placed"] and is_instance_valid(card["spawned"]):
			card["spawned"].position = board_to_world(pos)  # une tour ou une base suit sa carte

	# Cartes qui ont disparu de la table.
	for id in _cards.keys():
		if not seen.has(id):
			_on_card_removed(_cards[id])
			_cards.erase(id)


# ============================================================ règles des cartes
## Une carte vient d'être jouée (posée et immobile assez longtemps).
## Renvoie l'objet qui doit suivre la carte tant qu'elle reste posée (une tour, une base), sinon null.
## Pour ajouter une carte : ajoute sa famille dans cards.json, puis son "type" ici.
func _on_card_played(id: int, pos: Vector2, angle: float) -> Node3D:
	var family := _family_of(id)
	var player := owner_of(pos)
	var color := Color(family.get("color", "#ffffff"))
	if family.get("type", "") == "base":
		# La base du joueur de cette moitié apparaît sur la carte (même pendant une fin de partie).
		fortresses[player].place_at(board_to_world(pos))
		return fortresses[player]
	if game_over:
		return null
	match family.get("type", ""):
		"fireball":
			cast_fireball(player, board_to_world(pos), angle_to_direction(angle), color)
		"tower":
			var t: Node3D = TowerScene.instantiate()
			t.player = player
			t.color = color
			t.target = fortresses[1 - player]
			t.game = self
			t.position = board_to_world(pos)
			add_child(t)
			FX.burst(self, board_to_world(pos, 0.2), color, 30)
			return t
		_:
			push_warning("Carte %d : aucune famille dans cards.json" % id)
	return null


func _on_card_removed(card: Dictionary) -> void:
	card["marker"].queue_free()
	var spawned = card["spawned"]
	if is_instance_valid(spawned) and spawned.has_method("dismiss"):
		spawned.dismiss()  # la tour disparaît avec sa carte (une base, elle, reste où elle est)


func cast_fireball(player: int, from: Vector3, direction: Vector3, color := Color(1.0, 0.45, 0.1)) -> void:
	var fb: Node3D = FireballScene.instantiate()
	fb.owner_player = player
	fb.direction = direction
	fb.color = color
	fb.game = self
	fb.position = from + Vector3(0, 0.7, 0)
	add_child(fb)
	FX.burst(self, from + Vector3(0, 0.2, 0), color, 30)


func _on_fortress_destroyed(player: int) -> void:
	if game_over:
		return
	game_over = true
	for f in fortresses:
		f.invulnerable = true  # les projectiles encore en vol ne comptent plus
	_banner_label.text = "Joueur %d gagne !\nR pour rejouer" % (2 - player)


func _restart() -> void:
	game_over = false
	_banner_label.text = ""
	for f in fortresses:
		f.reset()
	# Les tours encore posées sur la table reviennent en jeu.
	for id in _cards:
		var card: Dictionary = _cards[id]
		if card["placed"] and not is_instance_valid(card["spawned"]) and _family_of(id).get("type") == "tower":
			card["placed"] = false


# ============================================================ anneau de charge sous chaque carte
## Crée l'anneau (scenes/anneau.tscn, modèle models/anneau.glb) à la couleur de la carte.
## Renvoie la fiche de la carte : {"marker", "mats", "placed", "spawned"}.
func _make_marker(id: int) -> Dictionary:
	var marker: Node3D = MarkerScene.instantiate()
	add_child(marker)
	var mats := Models.tint(marker, Color(_family_of(id).get("color", "#ffffff")))
	return {"marker": marker, "mats": mats, "placed": false, "spawned": null}


## L'anneau suit la carte, grossit et brille de plus en plus pendant la charge (progress de 0 à 1).
func _update_marker(card: Dictionary, pos: Vector2, angle: float, progress: float) -> void:
	var marker: Node3D = card["marker"]
	marker.position = board_to_world(pos, 0.04)
	marker.rotation.y = -deg_to_rad(angle)
	var s := lerpf(0.5, 1.0, progress)
	marker.scale = Vector3(s, 1.0, s)
	for mat in card["mats"]:
		mat.emission_energy_multiplier = lerpf(0.3, 3.0, progress)


# ============================================================ chaque image, clavier
func _process(_delta: float) -> void:
	if not _net.connected:
		_status_label.text = "En attente du tracker sur %s\n→ lance : python tracker.py --sim" % _net.url
	elif not _calibrated:
		_status_label.text = "Tracker connecté · pose les 4 marqueurs de coin"
	else:
		_status_label.text = "Tracker connecté · %d carte(s) sur la table · vue : %s" % [_cards.size(), view.view_name()]
		for f in fortresses:
			if not f.placed:
				_status_label.text += "\nJ%d : pose ta carte Base dans ta moitié (%s)" % [f.player + 1, "gauche" if f.player == 0 else "droite"]


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match event.keycode:
		KEY_C:
			view.next_view()
		KEY_R:
			_restart()
		KEY_B:  # test sans cartes : pose les 2 bases à leur place par défaut
			for f in fortresses:
				f.place_at(fortress_position(f.player))
		KEY_F:
			cast_fireball(0, fortress_position(0) + Vector3(1.6, 0, 0), Vector3.RIGHT)
		KEY_G:
			cast_fireball(1, fortress_position(1) - Vector3(1.6, 0, 0), Vector3.LEFT, Color(0.3, 0.6, 1.0))
