from django.shortcuts import render
from rest_framework import viewsets, serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from transactions.models import Deposit, Withdrawal, Balance
from .serializers import DepositSerializer, WithdrawalSerializer, BalanceSerializer
from .filters import DepositFilter, WithdrawalFilter
from decimal import Decimal
from .permissions import IsOwnerOrReadOnly

class DepositViewSet(viewsets.ModelViewSet):
    serializer_class = DepositSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DepositFilter
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return Deposit.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        print("Performing create for deposit")
        try:
            deposit = serializer.save(user=self.request.user)
            print(f"Deposit created: {deposit}")

        except serializers.ValidationError as e:
            print(f"Validation errors: {e.detail}")
            return Response(e.detail, status=400)

    def update(self, request, *args, **kwargs):
        """overrides defaults update method
        only works when deposit is unverified(is_verified=False)"""

        print("Performing update for deposit")
        try:
            instance = self.get_object()
            old_verified = instance.is_verified

            #  updated deposit is already verified, Not allowed
            print(f"previous deposit status: {old_verified} ")
            if old_verified:
                return Response("You can't update an already verified deposit.",status=status.HTTP_400_BAD_REQUEST)

            # overriding deposit update method
            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(instance,data=request.data,partial=partial)
            if serializer.is_valid():
                new_instance = serializer.save(user=self.request.user)
                print(f"Deposit updated: {new_instance}, Verified: {new_instance.is_verified}")
                return Response(serializer.data,status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except serializers.ValidationError as e:
            print(f"Validation errors: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """ 
        Overwrites the default destroy method. We want to make sure only staff can delete 
        a verified deposit while a user can delete their own unverified deposit
        """
        print("performing Delete for deposit")

        try:
            instance = self.get_object()

            if instance.is_verified:
                if not request.user.is_staff:
                    return Response(
                                {"detail": "You can't delete an already verified deposit."},
                                status=status.HTTP_403_FORBIDDEN,
                            )
                balance = Balance.objects.get(user=instance.user)
                balance.amount -= Decimal(instance.amount)
                balance.save()
                print(f"Balance updated by subtracting {instance.amount}. New balance: {balance.amount}, Deleted by: {request.user.email}")

            # Delete the deposit
            instance.delete()
            print("Deposit deleted")

            return Response(
                    {"detail": "Deposit deleted successfully."},
                    status=status.HTTP_204_NO_CONTENT,
                )
        except Exception as e:
            print(f"Deposit not verified: {e}")
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['GET'] , permission_classes=[IsAdminUser])
    def verify(self, request, pk):
        """Verify the status of a deposit by a staff/admin"""
        try:
            deposit = Deposit.objects.get(id=pk)
            if deposit.is_verified:
                return Response(
                    data={"message": "Deposit is initially verified!"},
                    status=status.HTTP_400_BAD_REQUEST
                    )

            # make deposit verified
            deposit.is_verified = True
            deposit.save()
            print(f"Deposit verified successfully amount {deposit.amount}")

            balance, created = Balance.objects.get_or_create(user=deposit.user)
            balance.amount += Decimal(deposit.amount)
            balance.save()
            print(f"Balance updated successfully new amount {deposit.amount},first time depositing:{created}")

            return Response(
                data={"message": "Deposit verified successfully", "new balance": balance.amount},
                status= status.HTTP_200_OK
            )
        except Exception as e:
            print(f"Deposit not verified: {e}")
            return Response(e, status=status.HTTP_400_BAD_REQUEST)


class WithdrawalViewSet(viewsets.ModelViewSet):
    serializer_class = WithdrawalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = WithdrawalFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Withdrawal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        print("Performing create for withdrawal")

        try:
            withdrawal = serializer.save(user=self.request.user)
            print(f"Withdrawal created: {withdrawal}")

        except serializers.ValidationError as e:
            print(f"Validation errors: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Only admin/staff can change a verified withdrawal amount from the admin panel"""
        instance = self.get_object()
        old_verified = instance.is_verified

        print(f"previous withdrawal status: {old_verified} ")
        if old_verified:
            return Response("You can't update an already verified withdraw.",status=status.HTTP_400_BAD_REQUEST)

        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        print("Performing update for withdrawal")
        try:
            new_instance = serializer.save(user=self.request.user)
            print(f"Withdrawal updated: {new_instance}, Verified: {new_instance.is_verified}")

        except serializers.ValidationError as e:
            print(f"Validation errors: {e.detail}")
            return Response(e.detail, status=400)
    
    def destroy(self, request, *args, **kwargs):
        """ 
        Overwrites the default destroy method. 
        we add to balance for deleted verified withdrawal.
        user can delete their own unverified withdrawal
        """
        print("performing Delete for withdrawal")

        try:
            instance = self.get_object()

            if instance.is_verified:
                if not request.user.is_staff:
                    return Response(
                                {"detail": "You can't delete an already verified withdrawal."},
                                status=status.HTTP_403_FORBIDDEN,
                            )
                balance = Balance.objects.get(user=instance.user)
                balance.amount += Decimal(instance.amount)
                balance.save()
                print(f"Balance updated by adding {instance.amount}. New balance: {balance.amount}, Deleted by: {request.user.email}")

            # Delete the deposit
            instance.delete()
            print("Withdrawal deleted")

            return Response(
                    {"detail": "Withdrawal deleted successfully."},
                    status=status.HTTP_204_NO_CONTENT,
                )
        except Exception as e:
            print(f"Withdrawal not verified: {e}")
            return Response(e, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['GET'] , permission_classes=[IsAdminUser])
    def verify(self, request, pk):
        """Verify the status of a Withdrawal by a staff/admin"""
        try:
            withdrawal = Withdrawal.objects.get(id=pk)
            if withdrawal.is_verified:
                return Response(
                    data={"message": "Deposit is initially verified!"},
                    status=status.HTTP_400_BAD_REQUEST
                    )

            # make deposit verified
            withdrawal.is_verified = True
            withdrawal.save()
            print(f"Deposit verified successfully amount {withdrawal.amount}")

            balance = Balance.objects.get(user=withdrawal.user)
            balance.amount -= Decimal(withdrawal.amount)
            balance.save()
            print(f"Balance updated successfully after withdraw new amount:{withdrawal.amount}")

            return Response(
                data={"message": "Withdrawal verified successfully", 
                      "Verified amount to be withdraw": withdrawal.amount,
                      "new balance":balance.amount},

                status= status.HTTP_200_OK
            )
        except Exception as e:
            print(f"Deposit not verified: {e}")
            return Response(e, status=status.HTTP_400_BAD_REQUEST)


class BalanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BalanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Balance.objects.all()
        return Balance.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if queryset.exists():
            serializer = self.get_serializer(queryset,many=True)
            return Response(serializer.data)
        else:
            return Response({"id": None, "user": request.user.id, "amount": 0})
