extends Node3D
## Tour : tant que la carte reste posée, tire régulièrement sur la base adverse.
## Le modèle 3D est dans models/tour.glb, la scène dans scenes/tour.tscn.

const Models := preload("res://scripts/models.gd")
const ProjectileScene := preload("res://scenes/projectile.tscn")

var player := 0
var color := Color(0.65, 0.35, 1.0)
var target: Node3D  # base adverse
var game: Node
var fire_interval := 2.0
var damage := 5

var _crystal: Node3D  # l'objet "Cristal" du modèle : il flotte et tourne
var _crystal_y := 0.0
var _cooldown := 1.0  # secondes avant le prochain tir
var _t := 0.0         # temps écoulé (pour l'animation)


func _ready() -> void:
	Models.tint($Modele, color)
	_crystal = $Modele.find_child("Cristal")  # null si tu l'as renommé dans Blender : pas d'animation
	if _crystal:
		_crystal_y = _crystal.position.y

	# Apparition : la tour "pousse" en 0,4 s.
	scale = Vector3.ONE * 0.01
	create_tween().tween_property(self, "scale", Vector3.ONE, 0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func _process(delta: float) -> void:
	_t += delta
	if _crystal:
		_crystal.position.y = _crystal_y + sin(_t * 3.0) * 0.08
		_crystal.rotate_y(delta * 2.0)
	if target == null or not target.is_target() or game.game_over:
		return
	# Tir régulier sur la base adverse, depuis le cristal (ou le haut de la tour).
	_cooldown -= delta
	if _cooldown <= 0.0:
		_cooldown = fire_interval
		var b: Node3D = ProjectileScene.instantiate()
		b.from = _crystal.global_position if _crystal else global_position + Vector3(0, 1.3, 0)
		b.target = target
		b.color = color
		b.damage = damage
		get_parent().add_child(b)


## Appelé quand la carte est retirée de la table.
func dismiss() -> void:
	set_process(false)
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector3.ONE * 0.01, 0.3)
	tw.tween_callback(queue_free)
