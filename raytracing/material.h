#ifndef MATERIAL_H
#define MATERIAL_H

#include "hittable.h"

// required in each object; describing the behavior when a ray hits (light reflects off object)
// ie how much light will be absorbed by the material 
class material {
  public:
    virtual ~material() = default;

    virtual bool scatter(
        const ray& r_in, const hit_record& rec, color& attenuation, ray& scattered
    ) const {
        return false;
    }
};

// lambertian material; light goes in all directions but for the sake of efficiency, goes in a random direction
class lambertian : public material {
  public:
    lambertian(const color& albedo) : albedo(albedo) {}

    bool scatter(const ray& r_in, const hit_record& rec, color& attenuation, ray& scattered)
    const override {

        /*
        ok so this part is is weird: the comented part treats all directions not in the sphere as possible light rays
        however, the uncommented uses lambertian bias. in real life, the angle between the light ray and normal contributes to how much light absorbed
        ie if the ray grazes the point, then very little of that lights radiance is reflected
        however, if a ray hits directly at the normal, then a LOT of light is reflected
        a possible fix is to replace the 0.5 with a dot product between the normal and the new ray
        however, a more efficient fix is to just favour rays that come from near the normal
        so adding rec.normal + random_unit_vector() does that, you can draw it out and rays towards the normal are ore favoured
        */
        // auto scatter_direction = random_on_hemisphere(rec.normal); // 

        auto scatter_direction = rec.normal + random_unit_vector(); // biased around surface normal
        scattered = ray(rec.p, scatter_direction);
        // Catch degenerate scatter direction
        if (scatter_direction.near_zero()) scatter_direction = rec.normal;
        
        attenuation = albedo;
        // for this strategy, we make it so scatter % is 100% and an attenuation is applied to the vector 
        // (absorbing light)
        return true;
    }

  private:
    color albedo;
};

// polished metal, ray is directly reflected across the normal
class metal : public material {
  public:
    // you can add a factor of randomness, which makes a metal more fuzzy and closer to a lambertian
    // note that a rough metal is NOT the same as a lambertian 
    // fuzz of 0 means pure metal
    metal(const color& albedo, double fuzz) : albedo(albedo), fuzz(fuzz < 1 ? fuzz : 1) {}

    bool scatter(const ray& r_in, const hit_record& rec, color& attenuation, ray& scattered)
    const override {
        vec3 reflected = reflect(r_in.direction(), rec.normal);
        reflected = unit_vector(reflected) + (fuzz * random_unit_vector());
        scattered = ray(rec.p, reflected);
        attenuation = albedo;
        return (dot(scattered.direction(), rec.normal) > 0);
    }

  private:
    color albedo;
    double fuzz;

};

class dielectric : public material {
  public:
    dielectric(double refraction_index) : refraction_index(refraction_index) {}

    bool scatter(const ray& r_in, const hit_record& rec, color& attenuation, ray& scattered)
    const override {
        attenuation = color(1.0, 1.0, 1.0);
        // if ray comes from air -> object vs from object -> air
        double ri = rec.front_face ? (1.0/refraction_index) : refraction_index;

        vec3 unit_direction = unit_vector(r_in.direction());
        double cos_theta = std::fmin(dot(-unit_direction, rec.normal), 1.0);
        double sin_theta = std::sqrt(1.0 - cos_theta*cos_theta);

        bool cannot_refract = ri * sin_theta > 1.0;
        vec3 direction;
        // total internal reflection, so just reflect. the second part is schlicks approximation which i don't understand
        if (cannot_refract || reflectance(cos_theta, ri) > random_double()) 
            direction = reflect(unit_direction, rec.normal);
        else
            direction = refract(unit_direction, rec.normal, ri);

        scattered = ray(rec.p, direction);
        
        return true;
    }

  private:
    // Refractive index in vacuum or air, or the ratio of the material's refractive index over
    // the refractive index of the enclosing media
    double refraction_index;

    static double reflectance(double cosine, double refraction_index) {
        // Use Schlick's approximation for reflectance.
        auto r0 = (1 - refraction_index) / (1 + refraction_index);
        r0 = r0*r0;
        return r0 + (1-r0)*std::pow((1 - cosine),5);
    }
};

#endif