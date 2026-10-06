/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

/**
 * Common beer styles as select options.
 * Format: { value, label } for use with AppSelect.
 */
interface BeerStyleOption {
  value: string
  label: string
}

export const beerStyleOptions: BeerStyleOption[] = [
  { value: '', label: '— Select style —' },
  // Lagers
  { value: 'american-lager', label: 'American Lager' },
  { value: 'munich-helles', label: 'Munich Helles' },
  { value: 'german-pilsner', label: 'German Pilsner' },
  { value: 'czech-pilsner', label: 'Czech Pilsner' },
  { value: 'oktoberfest', label: 'Oktoberfest / Märzen' },
  { value: 'munich-dunkel', label: 'Munich Dunkel' },
  { value: 'schwarzbier', label: 'Schwarzbier' },
  { value: 'bock', label: 'Bock' },
  { value: 'doppelbock', label: 'Doppelbock' },
  // Ales — British
  { value: 'english-bitter', label: 'English Bitter' },
  { value: 'english-pale-ale', label: 'English Pale Ale' },
  { value: 'english-ipa', label: 'English IPA' },
  { value: 'english-porter', label: 'English Porter' },
  { value: 'english-stout', label: 'English Stout' },
  { value: 'oatmeal-stout', label: 'Oatmeal Stout' },
  { value: 'imperial-stout', label: 'Imperial Stout' },
  { value: 'barleywine', label: 'Barleywine' },
  // Ales — American
  { value: 'american-pale-ale', label: 'American Pale Ale' },
  { value: 'american-ipa', label: 'American IPA' },
  { value: 'double-ipa', label: 'Double IPA' },
  { value: 'hazy-ipa', label: 'Hazy / New England IPA' },
  { value: 'american-amber', label: 'American Amber Ale' },
  { value: 'american-brown', label: 'American Brown Ale' },
  { value: 'american-stout', label: 'American Stout' },
  // Belgian
  { value: 'belgian-witbier', label: 'Belgian Witbier' },
  { value: 'belgian-blond', label: 'Belgian Blond Ale' },
  { value: 'belgian-tripel', label: 'Belgian Tripel' },
  { value: 'belgian-dubbel', label: 'Belgian Dubbel' },
  { value: 'belgian-quadrupel', label: 'Belgian Quadrupel' },
  { value: 'saison', label: 'Saison' },
  // German Ales
  { value: 'hefeweizen', label: 'Hefeweizen' },
  { value: 'dunkelweizen', label: 'Dunkelweizen' },
  { value: 'weizenbock', label: 'Weizenbock' },
  { value: 'kolsch', label: 'Kölsch' },
  { value: 'altbier', label: 'Altbier' },
  // Sour / Wild
  { value: 'berliner-weisse', label: 'Berliner Weisse' },
  { value: 'gose', label: 'Gose' },
  { value: 'lambic', label: 'Lambic' },
  { value: 'flanders-red', label: 'Flanders Red Ale' },
  // Cider / Other
  { value: 'cider', label: 'Cider' },
  { value: 'mead', label: 'Mead' },
  { value: 'other', label: 'Other' }
]
