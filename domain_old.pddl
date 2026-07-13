(define (domain industrial-monitor)

 (:requirements :strips :typing :negative-preconditions)

 (:types
    zone
 )

 (:predicates

    ;; ==================================
    ;; Environment predicates
    ;; ==================================

    (temp-high ?z - zone)

    (proximity-violation ?z - zone)

    (noise-high ?z - zone)

    (door-open ?z - zone)

    (occupied ?z - zone)

    ;; ==================================
    ;; Actuator predicates
    ;; ==================================

    (fan-on ?z - zone)

    (buzzer-on ?z - zone)

    (occupancy-led-on ?z - zone)

    (noise-warning-on ?z - zone)

    (door-alert-on ?z - zone)
 )

 ;; =====================================================
 ;; FAN
 ;; =====================================================

 (:action turn-on-fan

    :parameters (?z - zone)

    :precondition
       (and
          (temp-high ?z)
          (not (fan-on ?z))
       )

    :effect
       (fan-on ?z)
 )

 (:action turn-off-fan

    :parameters (?z - zone)

    :precondition
       (and
          (not (temp-high ?z))
          (fan-on ?z)
       )

    :effect
       (not (fan-on ?z))
 )

 ;; =====================================================
 ;; BUZZER
 ;; =====================================================

 (:action sound-buzzer

    :parameters (?z - zone)

    :precondition
       (and
          (proximity-violation ?z)
          (not (buzzer-on ?z))
       )

    :effect
       (buzzer-on ?z)
 )

 (:action stop-buzzer

    :parameters (?z - zone)

    :precondition
       (and
          (not (proximity-violation ?z))
          (buzzer-on ?z)
       )

    :effect
       (not (buzzer-on ?z))
 )

 ;; =====================================================
 ;; OCCUPANCY LED
 ;; =====================================================

 (:action light-occupancy-led

    :parameters (?z - zone)

    :precondition
       (and
          (occupied ?z)
          (not (occupancy-led-on ?z))
       )

    :effect
       (occupancy-led-on ?z)
 )

 (:action unlight-occupancy-led

    :parameters (?z - zone)

    :precondition
       (and
          (not (occupied ?z))
          (occupancy-led-on ?z)
       )

    :effect
       (not (occupancy-led-on ?z))
 )

 ;; =====================================================
 ;; NOISE WARNING
 ;; =====================================================

 (:action activate-noise-warning

    :parameters (?z - zone)

    :precondition
       (and
          (noise-high ?z)
          (not (noise-warning-on ?z))
       )

    :effect
       (noise-warning-on ?z)
 )

 (:action clear-noise-warning

    :parameters (?z - zone)

    :precondition
       (and
          (not (noise-high ?z))
          (noise-warning-on ?z)
       )

    :effect
       (not (noise-warning-on ?z))
 )

 ;; =====================================================
 ;; DOOR ALERT
 ;; =====================================================

 (:action activate-door-alert

    :parameters (?z - zone)

    :precondition
       (and
          (door-open ?z)
          (not (door-alert-on ?z))
       )

    :effect
       (door-alert-on ?z)
 )

 (:action clear-door-alert

    :parameters (?z - zone)

    :precondition
       (and
          (not (door-open ?z))
          (door-alert-on ?z)
       )

    :effect
       (not (door-alert-on ?z))
 )
)