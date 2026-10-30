import ModuleShell from '../../../app/layout/ModuleShell'

export default function EvaluatorHome() {
  return (
    <ModuleShell
      title="Evaluator"
      description="Lets approved evaluators take gig-based inspection assignments, complete structured checklists with verified photos and location, and get paid for valid inspections."
      owners="Ibrahim (integration), Shabaz (auth & biometrics), Shubham (allocation & fraud logic)"
      plannedFeatures={[
        'Evaluator registration and admin approval',
        'Gig-based inspection assignments with 45-day evaluator–toilet cooldown',
        'Structured checklist with in-app camera',
        'GPS, timestamp and duplicate-image checks; AI-assisted fraud screening',
        'Device biometrics and payment for valid inspections',
      ]}
    />
  )
}
