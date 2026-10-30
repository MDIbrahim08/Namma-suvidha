import ModuleShell from '../../../app/layout/ModuleShell'

export default function GovernmentHome() {
  return (
    <ModuleShell
      title="Government"
      description="Gives sanitation authorities a single view of facility condition, inspections and citizen feedback, and tracks every reported issue through acknowledgement to resolution."
      owners="Ibrahim"
      plannedFeatures={[
        'Facility monitoring with weighted facility scores',
        'Review of inspections and citizen feedback',
        'Recurring-issue detection and maintenance reports',
        'Email/SMS notifications to authorities',
        'Acknowledgement and resolution tracking',
      ]}
    />
  )
}
