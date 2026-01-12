module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.28"

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  eks_managed_node_groups = {
    main = {
      min_size       = 2
      max_size       = 5
      desired_size   = 2
      instance_types = ["t3.medium"]

      labels = {
        Environment = var.environment
      }
    }
  }

  # Enable IRSA for pod-level AWS permissions
  enable_irsa = true
}
