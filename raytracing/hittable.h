// hittable: an abstract class for primitatives which allows any ray to check if it hits. 
// expects the child classes to implement the hit and modify a hit_record object
#ifndef HITTABLE_H
#define HITTABLE_H

#include "ray.h"

class material;

class hit_record {
  public:
    point3 p;
    vec3 normal;
    shared_ptr<material> mat;
    double t;
    bool front_face;

    void set_face_normal(const ray& r, const vec3& outward_normal) {
        // Sets the hit record normal vector.
        // NOTE: the parameter `outward_normal` is assumed to have unit length.

         // if the dot is less than 0, then angle is obtuse -> outside hit 
         // if the angle is > 0, then angle is acute -> inside hit 
        front_face = dot(r.direction(), outward_normal) < 0;
        normal = front_face ? outward_normal : -outward_normal;
    }
};

class hittable {
  public:
    virtual ~hittable() = default; // destructor

    virtual bool hit(const ray& r, interval ray_t, hit_record& rec) const = 0; // virtual function, expect an implementation
};

#endif