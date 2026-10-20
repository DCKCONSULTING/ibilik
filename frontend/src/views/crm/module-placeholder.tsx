import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const ModulePlaceholder = ({
  title,
  description
}: {
  title: string
  description: string
}) => {
  return (
    <Card className='shadow-none'>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className='text-muted-foreground text-sm'>
        This section is available to your account. Operational records will appear here as iBilik CRM modules are
        connected. Access is still enforced by Django if the matching API is called directly.
      </CardContent>
    </Card>
  )
}

export default ModulePlaceholder
