extends Node3D
## Projectile de tour : vole en cloche jusqu'à la base visée.
## Le modèle 3D est dans models/projectile.glb, la scène dans scenes/projectile.tscn.

const Models := preload("res://scripts/models.gd")
const FX := preload("res://scripts/fx.gd")

var from := Vector3.ZERO
var target: Node3D
var color := Color.WHITE
var damage := 5

var _t := 0.0            # avancement du vol, de 0 (départ) à 1 (arrivée)
var _duration := 1.0     # durée du vol (secondes)
var _end := Vector3.ZERO # point d'arrivée


func _ready() -> void:
	Models.tint($Modele, color.lightened(0.3))
	add_child(FX.trail(color, 0.6))  # traînée de particules (effet, pas un modèle)
	_end = target.global_position + Vector3(0, 1.2, 0)
	_duration = clampf(from.distance_to(_end) / 8.0, 0.4, 1.5)
	global_position = from


func _process(delta: float) -> void:
	_t = minf(1.0, _t + delta / _duration)
	var p := from.lerp(_end, _t)
	p.y += sin(_t * PI) * 1.5  # trajectoire en cloche
	global_position = p
	if _t >= 1.0:
		if is_instance_valid(target):
			target.take_damage(damage)
		FX.explosion(get_parent(), global_position, color, 0.4)
		queue_free()
