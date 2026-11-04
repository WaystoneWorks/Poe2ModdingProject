import { describe, expect, it } from 'vitest';
import { parseQuery, resolveStatus, rowMatches, sectionMatches, toggleIs } from './filter';
import { pct, tally } from './progress';
import type { RowTuple } from './types';

const row = (status: RowTuple[3], name = 'Fireball'): RowTuple => ['gem:x', 'Intelligence', name, status, 'a note', '', false];

describe('query', () => {
  it('parses terms, is, -is and in', () => {
    const q = parseQuery('fireball is:implemented -is:fully_functional in:gems');
    expect(q).toEqual({ terms: ['fireball'], is: ['implemented'], notIs: ['fully_functional'], in: ['gems'] });
  });
  it('resolves prefixes and separators', () => {
    expect(resolveStatus('fully')).toBe('fully_functional');
    expect(resolveStatus('not-planned')).toBe('not_planned');
    expect(resolveStatus('not')).toBeNull(); // not_implemented or not_planned
    expect(resolveStatus('impl')).toBe('implemented');
  });
  it('keeps an unknown is: value as a term', () => {
    expect(parseQuery('is:nonsense').terms).toEqual(['is:nonsense']);
  });
  it('matches rows', () => {
    expect(rowMatches(parseQuery('fire'), row('partial'))).toBe(true);
    expect(rowMatches(parseQuery('ice'), row('partial'))).toBe(false);
    expect(rowMatches(parseQuery('is:partial'), row('partial'))).toBe(true);
    expect(rowMatches(parseQuery('-is:partial'), row('partial'))).toBe(false);
    expect(rowMatches(parseQuery('note'), row('unknown'))).toBe(true);
  });
  it('matches sections', () => {
    expect(sectionMatches(parseQuery('in:gem'), { id: 'gems', title: 'Skill gems' })).toBe(true);
    expect(sectionMatches(parseQuery('in:unique'), { id: 'gems', title: 'Skill gems' })).toBe(false);
  });
  it('toggles is:', () => {
    expect(toggleIs('a', 'partial')).toBe('a is:partial');
    expect(toggleIs('a is:partial', 'partial')).toBe('a');
  });
});

describe('progress', () => {
  it('weights rows equally and leaves out not planned', () => {
    const t = tally([row('fully_functional'), row('unknown'), row('not_planned'), row('partial')]);
    expect(t.total).toBe(3);
    expect(t.done).toBe(1.5);
    expect(t.percent).toBe(50);
  });
  it('formats percentages', () => {
    expect(pct(0)).toBe('0%');
    expect(pct(0.04)).toBe('<0.1%');
    expect(pct(12.43)).toBe('12%');
    expect(pct(3.26)).toBe('3.3%');
  });
});
