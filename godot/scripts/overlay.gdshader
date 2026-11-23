// Pose l'image 3D sur la vidéo, avec une petite correction de perspective.
//
// Pour chaque point de l'écran (UV, de 0 à 1), la matrice row0/row1/row2 (envoyée par
// le tracker) dit quel point de l'image 3D afficher. C'est ce qui fait tomber le plateau
// pile sur les 4 marqueurs de coin, même si la caméra 3D n'est pas parfaitement placée.
shader_type canvas_item;

uniform vec3 row0 = vec3(1.0, 0.0, 0.0);
uniform vec3 row1 = vec3(0.0, 1.0, 0.0);
uniform vec3 row2 = vec3(0.0, 0.0, 1.0);

void fragment() {
	vec3 p = vec3(UV, 1.0);
	vec3 q = vec3(dot(row0, p), dot(row1, p), dot(row2, p));
	vec2 source = q.xy / q.z;
	bool outside = q.z <= 0.0 || source.x < 0.0 || source.y < 0.0 || source.x > 1.0 || source.y > 1.0;
	COLOR = outside ? vec4(0.0) : texture(TEXTURE, source);
}
