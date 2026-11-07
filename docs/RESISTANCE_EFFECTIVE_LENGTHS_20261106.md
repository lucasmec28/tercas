# Recovered resistance-only effective lengths

Restored explicitly after executor loss. This reconstructs the behavior of lost
commit 8608350 on recovered base fcd2671; it is not byte-identical recovery and
its tests must be rerun. The previous 64 passing tests do not certify these bytes.

Physical L remains unchanged for demands, load stations, deflection and Vlasov.
Fresh Annex E weak-reference calculation reads existing weak_catalog.Lx_mm and
single [0,L] segment effective Ly/Lz plus its already declared origin. No retyping,
new approval, fictitious support or automatic migration of input is introduced.
Flange-specific Ly fields take precedence; unequal flanges/multiple segments are
not adapted by this first policy. The optional declare API is additive, not a
requirement to reenter existing values. All declared lengths are positive finite.

Generic helper: resistance_effective_lengths.configuration and annex_e_forces.
Nex = pi² E Ix/Lx²; Nez = (GJ+pi² E Cw/Lz²)/r0².
Existing signed Annex E Me = Nex/Cm*(sqrt(j²+r0² Nez/Nex)+Cs*j), Cm=1.
The own-contour weak provider retains its existing section/material/sign domain.
No Ue125 resistance qualification is extended to another family member by name.

New Annex E and positive certificates have explicit effective-length schemas.
Historical v1 validation reconstructs its original full-span policy even when
old input carried smaller lengths. The test includes surviving actual git-show
base modules, not only the reconstructed implementation's historical switch.
Both old full certificates and hashes are compared as canonical JSON bytes.

Saved-note helper exposes physical L and weak Lx/Lz in UI/Word, from the snapshot
alone. It explicitly states that the strong-height component still uses full L.
No strong-height eigenoperator or demand calculation is changed.

NBR14762:2010 9.7.2.1 pp41–42; 9.8.2.2 p48; Annex E.2 p82:
classic strong Me=Cb*pi/Ly*sqrt(EIy*(GJ+pi²ECw/Lz²)). Section9.8.2.2 derives
expressions for load at CT and allows conservative use for stabilizing position;
destabilizing position refers to specialized bibliography. This is a method
coverage gap, not a requirement to draw intermediate supports or to use FEM.
The strong-height solver uses L simultaneously for basis, stiffness, M(s),
point positions and height terms; substituting Leff for L is not justified.

Normative public sources checked by independent reviewer before loss:
https://www.academia.edu/9135392/Dimensionamento_de_estruturas_de_a%C3%A7o_constitu%C3%ADdas_por_perfis_formados_a_frio_Design_of_cold_formed_steel_structures
https://www.passeidireto.com/arquivo/87201775/abnt-nbr-14762-2010-dimensionamento-de-estruturas-de-aco-constituidas-por-perfis

No private project, solver, publication or historical reclassification.
