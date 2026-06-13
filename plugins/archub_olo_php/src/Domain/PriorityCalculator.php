<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Domain;

use DateTimeImmutable;

/**
 * Computes the MyLifeOrganized-style "computed priority" for a task.
 *
 * In OLO/MLO the priority shown in the To-Do list is not entered by hand: it is
 * derived from the task's own importance and urgency, amplified by how close the
 * due date is. This calculator reproduces that behaviour, yielding a 0..100
 * score and a 0..5 star rating used to rank the smart "To-Do" view.
 */
final readonly class PriorityCalculator
{
    public function __construct(private DateTimeImmutable $now)
    {
    }

    /**
     * @return array{score:float,stars:int,due_state:string,days_to_due:?int}
     */
    public function evaluate(Task $task): array
    {
        $importance = $this->clamp($task->importance);
        $urgency = $this->clamp($task->urgency);

        // Base blend: importance dominates, urgency modulates (MLO weighting).
        $score = 0.6 * $importance + 0.4 * $urgency;

        [$dueState, $daysToDue] = $this->dueState($task);

        // Due-date amplification, the signature of the computed priority.
        $score += match ($dueState) {
            'overdue' => 35.0,
            'due_today' => 25.0,
            'due_soon' => 15.0,
            'upcoming' => 5.0,
            default => 0.0,
        };

        if ($task->starred) {
            $score += 10.0;
        }
        if ($task->isCompleted()) {
            $score = 0.0;
        }

        $score = max(0.0, min(100.0, $score));

        return [
            'score' => round($score, 1),
            'stars' => (int) round($score / 20.0),
            'due_state' => $dueState,
            'days_to_due' => $daysToDue,
        ];
    }

    /**
     * @return array{0:string,1:?int}
     */
    private function dueState(Task $task): array
    {
        if ($task->dueAt === null) {
            return ['none', null];
        }
        // Compare by calendar day so "overdue" agrees with the Overdue view:
        // a task due yesterday evening is overdue this morning, not "due today".
        $today = $this->now->setTime(0, 0);
        $dueDay = (new DateTimeImmutable($task->dueAt))->setTime(0, 0);
        $days = (int) $today->diff($dueDay)->format('%r%a');

        if ($task->isCompleted()) {
            return ['done', $days];
        }
        if ($days < 0) {
            return ['overdue', $days];
        }
        if ($days === 0) {
            return ['due_today', 0];
        }
        if ($days <= 3) {
            return ['due_soon', $days];
        }

        return ['upcoming', $days];
    }

    private function clamp(int $value): float
    {
        return (float) max(0, min(100, $value));
    }
}
