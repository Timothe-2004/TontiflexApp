"""
Exceptions personnalisées pour le module Mobile Money de TontiFlex.
"""


class MobileMoneyServiceException(Exception):
    """Exception de base pour tous les erreurs du service Mobile Money."""
    pass


class OperateurNonSupporte(MobileMoneyServiceException):
    """Levée quand l'opérateur Mobile Money n'est pas supporté."""
    pass


class MontantInvalide(MobileMoneyServiceException):
    """Levée quand le montant de la transaction est invalide."""
    pass


class NumeroTelephoneInvalide(MobileMoneyServiceException):
    """Levée quand le numéro de téléphone n'est pas valide."""
    pass


class ErreurAPI(MobileMoneyServiceException):
    """Levée quand il y a une erreur lors de l'appel à l'API Mobile Money."""
    pass


class TransactionExpire(MobileMoneyServiceException):
    """Levée quand une transaction Mobile Money a expiré."""
    pass


class TransactionEchouee(MobileMoneyServiceException):
    """Levée quand une transaction Mobile Money a échoué."""
    pass


class SoldInsuffisant(MobileMoneyServiceException):
    """Levée quand le solde du compte Mobile Money est insuffisant."""
    pass


class LimiteJournaliereDépassée(MobileMoneyServiceException):
    """Levée quand la limite journalière de transaction est dépassée."""
    pass


class CompteBloque(MobileMoneyServiceException):
    """Levée quand le compte Mobile Money est bloqué."""
    pass


class CodePINIncorrect(MobileMoneyServiceException):
    """Levée quand le code PIN saisi est incorrect."""
    pass
