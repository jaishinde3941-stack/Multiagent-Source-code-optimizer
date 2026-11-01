// Category: Logic Errors
// Error: Wrong logical operator (AND vs OR)

#include <iostream>

bool isValidAge(int age) {
    // ERROR: Should be && (AND), not || (OR)
    return age >= 0 || age <= 120;  // Always returns true!
}

int main() {
    int age = -5;
    
    if (isValidAge(age)) {
        std::cout << "Valid age: " << age << std::endl;  // Will print for -5!
    }
    
    return 0;
}
