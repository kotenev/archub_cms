<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Domain;

use DateInterval;
use DateTimeImmutable;

/**
 * Recurrence rule for a task, mirroring the OLO domain events
 * `TaskRecurrenceSet` / `TaskRecurrenceAdvanced`.
 *
 * Supports a pragmatic subset of RFC 5545 RRULE (FREQ + INTERVAL) and the two
 * OLO recurrence modes:
 *  - FROM_DUE      — the next occurrence is computed from the previous due date
 *                    (fixed-cadence schedules such as "pay rent on the 1st").
 *  - FROM_COMPLETE — the next occurrence is computed from completion time
 *                    (floating habits such as "water the plants every 3 days").
 */
final readonly class Recurrence
{
    public const MODE_FROM_DUE = 'FROM_DUE';
    public const MODE_FROM_COMPLETE = 'FROM_COMPLETE';

    public function __construct(
        public string $rrule,
        public string $mode,
    ) {
    }

    public static function fromArray(?array $data): ?self
    {
        if ($data === null || !isset($data['rrule'])) {
            return null;
        }
        return new self((string) $data['rrule'], (string) ($data['mode'] ?? self::MODE_FROM_DUE));
    }

    public function toArray(): array
    {
        return ['rrule' => $this->rrule, 'mode' => $this->mode];
    }

    /**
     * Compute the next occurrence after $base according to the rule.
     * $base is the previous due date (FROM_DUE) or the completion time
     * (FROM_COMPLETE), resolved by the caller.
     */
    public function next(DateTimeImmutable $base): DateTimeImmutable
    {
        $parts = $this->parse();
        $interval = max(1, (int) ($parts['INTERVAL'] ?? 1));
        $freq = strtoupper((string) ($parts['FREQ'] ?? 'DAILY'));

        return match ($freq) {
            'DAILY' => $base->add(new DateInterval("P{$interval}D")),
            'WEEKLY' => $base->add(new DateInterval('P' . ($interval * 7) . 'D')),
            'MONTHLY' => $base->add(new DateInterval("P{$interval}M")),
            'YEARLY' => $base->add(new DateInterval("P{$interval}Y")),
            default => $base->add(new DateInterval("P{$interval}D")),
        };
    }

    public function humanReadable(): string
    {
        $parts = $this->parse();
        $interval = max(1, (int) ($parts['INTERVAL'] ?? 1));
        $freq = strtolower((string) ($parts['FREQ'] ?? 'daily'));
        $unit = match ($freq) {
            'daily' => 'day',
            'weekly' => 'week',
            'monthly' => 'month',
            'yearly' => 'year',
            default => $freq,
        };
        $cadence = $interval === 1 ? "every {$unit}" : "every {$interval} {$unit}s";
        $mode = $this->mode === self::MODE_FROM_COMPLETE ? 'from completion' : 'from due date';

        return "{$cadence} ({$mode})";
    }

    /** @return array<string,string> */
    private function parse(): array
    {
        $out = [];
        foreach (explode(';', $this->rrule) as $segment) {
            if (str_contains($segment, '=')) {
                [$key, $value] = explode('=', $segment, 2);
                $out[strtoupper(trim($key))] = trim($value);
            }
        }
        return $out;
    }
}
