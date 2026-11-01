// Category: Logic Errors (Success Case)
// Expected Result: Use correct logical operator

#include <iostream>

bool isValidAge(int age) {
    // SUCCESS: Used && (AND) for range check
    return age >= 0 && age <= 120;
}

int main() {
    int age = -5;
    
    if (isValidAge(age)) {
        std::cout << "Valid age: " << age << std::endl;
    } else {
        std::cout << "Invalid age: " << age << std::endl;  // SUCCESS: Correctly rejected
    }
    
    return 0;
}
