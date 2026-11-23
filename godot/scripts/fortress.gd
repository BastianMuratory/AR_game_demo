extends Node3D
## Base (forteresse) d'un joueur : points de vie et position sur la table.
## Le modèle 3D est dans models/base.glb, la scène dans scenes/base.tscn.
##
## La base n'existe dans le jeu qu'une fois sa carte "Base" posée sur la table (voir main.gd).

signal destroyed(player: int)  # envoyé quand les PV tombent à 0

const Models := preload("res://scripts/models.gd")
const FX := preload("res://scripts/fx.gd")
const MAX_HP := 100

var player := 0
var color := Color.WHITE
var radius := 1.5   # rayon de collision au sol (unités Godot)
var hp := MAX_HP
var alive := true
var placed := false        # true dès que la carte Base a été posée
var invulnerable := false  # mis à true à la fin de la partie

@onready var _model: Node3D = $Modele  # le château importé (secoué quand il est touché)
@onready var _label: Label3D = $Texte  # "J1 · 100 PV" au-dessus du château


func _ready() -> void:
	Models.tint(_model, color)  # toits à la couleur du joueur
	visible = false             # invisible tant que la carte n'est pas posée
	_refresh()


## Appelé quand la carte Base est posée (ou déplacée) sur la table.
func place_at(pos: Vector3) -> void:
	position = pos
	if placed:
		return
	placed = true
	visible = true
	# Apparition : le château sort de la table.
	_model.position.y = -2.5
	create_tween().tween_property(_model, "position:y", 0.0, 0.6).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	FX.burst(get_parent(), pos + Vector3(0, 0.2, 0), color, 40)


## Vrai si cette base peut être visée (posée et encore debout).
func is_target() -> bool:
	return placed and alive


func _refresh() -> void:
	_label.text = "J%d · %d PV" % [player + 1, hp] if alive else "J%d · détruite !" % [player + 1]
	_label.modulate = color.lightened(0.3)


func take_damage(amount: int) -> void:
	if not is_target() or invulnerable:
		return
	hp = maxi(0, hp - amount)
	# petit "coup" visuel
	_model.scale = Vector3(1.12, 0.85, 1.12)
	create_tween().tween_property(_model, "scale", Vector3.ONE, 0.3).set_trans(Tween.TRANS_ELASTIC)
	_refresh()
	if hp == 0:  # détruite : explosion, le château s'enfonce dans la table
		alive = false
		_refresh()
		FX.explosion(get_parent(), global_position + Vector3(0, 1, 0), color, 2.5)
		var tw := create_tween()
		tw.tween_property(_model, "position:y", -3.0, 2.0).set_trans(Tween.TRANS_QUAD)
		tw.tween_callback(_model.hide)  # sous la table : on le cache (sinon il se voit par-dessus la vidéo)
		destroyed.emit(player)


## Nouvelle partie (la base reste où sa carte est posée).
func reset() -> void:
	hp = MAX_HP
	alive = true
	invulnerable = false
	_model.position = Vector3.ZERO
	_model.show()
	_refresh()
