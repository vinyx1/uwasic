# Ray Tracer

A small CPU ray tracer written in C++17, built by following Peter Shirley's
[_Ray Tracing in One Weekend_](https://raytracing.github.io/books/RayTracingInOneWeekend.html).
It renders a scene of randomly placed spheres and writes it out as a PPM image.

## Features

- Spheres with ray–sphere intersection
- Materials:
  - **Lambertian** (matte/diffuse)
  - **Metal** (reflective, with adjustable fuzz)
  - **Dielectric** (glass, with refraction and Schlick reflectance)
- Positionable camera (`lookfrom`, `lookat`, `vup`, adjustable field of view)
- Defocus blur (depth of field)
- Antialiasing via multiple samples per pixel
- Gamma correction

## Building

Requires CMake 3.10+ and a C++17 compiler.

```sh
cmake -B build
cmake --build build
```

## Running

The renderer writes the image to stdout and progress to stderr, so redirect
the output to a file:

```sh
./build/raytracing > image.ppm
```

Most image viewers open `.ppm` files directly (Preview on macOS does). To
convert to PNG instead, use something like ImageMagick:

```sh
magick image.ppm image.png
```

## Configuring the render

Scene and camera settings live in `main.cc`:

| Setting             | Default | Notes                                       |
| ------------------- | ------- | ------------------------------------------- |
| `image_width`       | 400     | Use 1200 for a final-quality render         |
| `samples_per_pixel` | 10      | More samples means less noise but a slower render |
| `max_depth`         | 10      | Max ray bounces; 50 for higher quality      |
| `vfov`              | 20      | Vertical field of view, in degrees          |
| `defocus_angle`     | 0.6     | 0 turns off depth of field                  |
| `focus_dist`        | 10.0    | Distance to the plane of perfect focus      |

## Project layout

| File              | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `main.cc`         | Builds the scene and sets up the camera              |
| `camera.h`        | Generates rays, renders pixels, writes the image     |
| `material.h`      | Lambertian, metal and dielectric materials           |
| `sphere.h`        | Sphere geometry and intersection                     |
| `hittable.h`      | Base interface for objects a ray can hit             |
| `hittable_list.h` | A collection of hittable objects (the world)         |
| `ray.h`           | Ray class                                            |
| `vec3.h`          | 3D vector math (also used for points and colors)     |
| `color.h`         | Color output with gamma correction                   |
| `interval.h`      | Real-valued interval helper                          |
| `rtheaders.h`     | Common includes, constants and utility functions     |
