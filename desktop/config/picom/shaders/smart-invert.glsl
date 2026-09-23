#version 330
// "Dark mode" for apps that have none (used for Zoom's main window only).
// invert() + hue-rotate(180deg), the same trick as browser dark-mode extensions:
// white -> black, black -> white, but blues stay blue and reds stay red.
in vec2 texcoord;
uniform sampler2D tex;
uniform float opacity;

vec4 default_post_processing(vec4 c);

vec4 window_shader() {
    vec4 c = texelFetch(tex, ivec2(texcoord), 0);
    vec3 inv = vec3(1.0) - c.rgb;
    // CSS hue-rotate(180deg) matrix; rows sum to 1, so greys stay grey
    vec3 rot = vec3(
        dot(inv, vec3(-0.574, 1.430, 0.144)),
        dot(inv, vec3( 0.426, 0.430, 0.144)),
        dot(inv, vec3( 0.426, 1.430, -0.856))
    );
    c.rgb = clamp(rot, 0.0, 1.0);
    return default_post_processing(c);
}
